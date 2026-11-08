import pytest
import json
import tomllib
from pathlib import Path

from pydantic import ValidationError

from aerolm.data.generate import generate_split
from aerolm.training import TrainingConfig, load_training_data, training_examples, validate_resume
from aerolm.data.generate import generate_dataset


class TokenizerStub:
    eos_token = "<|im_end|>"

    def apply_chat_template(self, messages, **kwargs):
        assert kwargs["enable_thinking"] is False
        return (
            "system: "
            + messages[0]["content"]
            + "\nuser: "
            + messages[1]["content"]
            + "\nassistant: "
        )

    def encode(self, text, **kwargs):
        return list(text)


def test_completion_contains_only_target_and_eos():
    rows = generate_split("train", 2, 42)
    examples = training_examples(rows, TokenizerStub(), 20000)
    assert len(examples) == 2
    assert "Subject:" in examples[0]["prompt"] or rows[0]["text"] in examples[0]["prompt"]
    assert examples[0]["completion"].startswith('{"request_type":"charter"')
    assert examples[0]["completion"].endswith("<|im_end|>")
    assert "prompt" not in examples[0]["completion"]


def test_training_refuses_silent_target_truncation():
    with pytest.raises(ValueError, match="instead of truncating"):
        training_examples(generate_split("train", 1, 42), TokenizerStub(), 10)


def test_pinned_configs_and_invalid_backend():
    for path in Path("configs").glob("*.toml"):
        config = TrainingConfig.model_validate(tomllib.loads(path.read_text()))
        assert len(config.revision) == 40
    data = config.model_dump()
    data["backend"] = "typo"
    with pytest.raises(ValidationError):
        TrainingConfig.model_validate(data)


def test_training_rejects_tampering_and_never_reads_test_data(tmp_path):
    generate_dataset(tmp_path, train=5, validation=3, test=2)
    (tmp_path / "test.jsonl").write_text("intentionally not JSON")
    manifest, rows = load_training_data(tmp_path)
    assert len(rows["train"]) == manifest["splits"]["train"]["count"]
    path = tmp_path / "train.jsonl"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="differs from manifest"):
        load_training_data(tmp_path)


def test_resume_rejects_changed_recipe(tmp_path):
    checkpoint = tmp_path / "checkpoint-10"
    checkpoint.mkdir()
    (tmp_path / "run_manifest.json").write_text(
        json.dumps(
            {
                "config_sha256": "original",
                "dataset_manifest": {"seed": 42},
            }
        )
    )
    validate_resume(tmp_path, str(checkpoint), "original", {"seed": 42})
    with pytest.raises(ValueError, match="original config"):
        validate_resume(tmp_path, str(checkpoint), "changed", {"seed": 42})


@pytest.mark.parametrize(
    "changes",
    [
        {"load_in_4bit": True},
        {"backend": "unsloth"},
        {"precision": "float16"},
    ],
)
def test_cpu_training_rejects_unsupported_modes(changes):
    config = tomllib.loads(Path("configs/cpu-lora.toml").read_text())
    with pytest.raises(ValidationError, match="CPU training supports"):
        TrainingConfig.model_validate({**config, **changes})


def test_cpu_recipe_is_explicit_and_preserves_cuda_defaults():
    config = TrainingConfig.model_validate(tomllib.loads(Path("configs/cpu-lora.toml").read_text()))
    assert config.device == "cpu" and config.precision == "bfloat16"
    assert not config.load_in_4bit and not config.gradient_checkpointing
    cuda = TrainingConfig.model_validate(tomllib.loads(Path("configs/qlora.toml").read_text()))
    assert cuda.device == "cuda" and cuda.load_in_4bit
