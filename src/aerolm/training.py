"""Completion-only supervised LoRA training, with optional 4-bit loading and Unsloth."""

import importlib.metadata
import hashlib
import json
import platform
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aerolm.domains.registry import registry
from aerolm.data.generate import sha256
from aerolm.evaluation import load_rows

TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


class TrainingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    backend: Literal["transformers", "unsloth"]
    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    seed: int = Field(ge=0, le=2**32 - 1)
    load_in_4bit: bool
    max_length: int = Field(ge=128, le=32768)
    lora_r: int = Field(ge=1, le=256)
    lora_alpha: int = Field(ge=1, le=1024)
    epochs: float = Field(gt=0)
    learning_rate: float = Field(gt=0, le=1)
    batch_size: int = Field(ge=1)
    gradient_accumulation_steps: int = Field(ge=1)
    device: Literal["cpu", "cuda"] = "cuda"
    precision: Literal["auto", "float32", "bfloat16", "float16"] = "auto"
    cpu_threads: int = Field(default=8, ge=1, le=256)
    gradient_checkpointing: bool = True
    logging_steps: int = Field(default=10, ge=1)
    eval_strategy: Literal["epoch", "no"] = "epoch"
    save_strategy: Literal["epoch", "steps"] = "epoch"
    save_steps: int = Field(default=50, ge=1)
    track_token_metrics: bool = True

    @model_validator(mode="after")
    def supported_device_settings(self) -> "TrainingConfig":
        if self.device == "cpu" and (
            self.load_in_4bit or self.backend == "unsloth" or self.precision == "float16"
        ):
            raise ValueError(
                "CPU training supports unquantized Transformers LoRA in float32/bfloat16"
            )
        return self


def load_training_data(data_dir: Path) -> tuple[dict, dict[str, list[dict]]]:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = {}
    for split in ("train", "validation"):
        path = data_dir / f"{split}.jsonl"
        if sha256(path) != manifest["splits"][split]["sha256"]:
            raise ValueError(f"{split} dataset differs from manifest")
        rows[split] = load_rows(path)
        if len(rows[split]) != manifest["splits"][split]["count"]:
            raise ValueError(f"{split} count differs from manifest")
        if any(row["split"] != split for row in rows[split]):
            raise ValueError("Wrong split in training input")
    if {r["text"] for r in rows["train"]} & {r["text"] for r in rows["validation"]}:
        raise ValueError("Train/validation leakage")
    if {r["template_family"] for r in rows["train"]} & {
        r["template_family"] for r in rows["validation"]
    }:
        raise ValueError("Train/validation template-family leakage")
    return manifest, rows


def validate_resume(output: Path, resume: str, config_hash: str, manifest: dict) -> dict:
    previous = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    if not Path(resume).is_dir():
        raise ValueError("Resume checkpoint directory does not exist")
    if previous["config_sha256"] != config_hash or previous["dataset_manifest"] != manifest:
        raise ValueError("Resume requires the original config and dataset manifest")
    return previous


def training_examples(rows: list[dict], tokenizer, max_length: int) -> list[dict]:
    spec = registry.get("charter")
    examples = []
    for row in rows:
        prompt = tokenizer.apply_chat_template(
            spec.messages(row["text"]),
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        completion = json.dumps(row["expected"], separators=(",", ":")) + tokenizer.eos_token
        if len(tokenizer.encode(prompt + completion, add_special_tokens=False)) > max_length:
            raise ValueError(
                f"{row['id']} exceeds max_length; increase it instead of truncating labels"
            )
        examples.append({"prompt": prompt, "completion": completion})
    return examples


def train(
    config_path: Path, data_dir: Path, output: Path, max_steps: int = -1, resume: str | None = None
) -> dict:
    config = TrainingConfig.model_validate(
        tomllib.loads(config_path.read_text(encoding="utf-8"))
    ).model_dump()
    manifest, rows = load_training_data(data_dir)
    previous = validate_resume(output, resume, sha256(config_path), manifest) if resume else None
    if output.exists() and any(output.iterdir()) and not resume:
        raise ValueError("Output is nonempty; use a new directory or --resume checkpoint path")
    # Must happen before torch/transformers/trl imports for Unsloth patches.
    if config["backend"] == "unsloth":
        from unsloth import FastLanguageModel
    import torch
    from datasets import Dataset
    from huggingface_hub import model_info
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed
    from trl import SFTConfig, SFTTrainer
    from transformers import TrainerCallback
    from time import perf_counter

    device = config["device"]
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable. Use configs/cpu-lora.toml for explicit CPU training.")
    if device == "cpu":
        torch.set_num_threads(config["cpu_threads"])
    revision = model_info(config["model_id"], revision=config["revision"]).sha
    if previous and (previous["model_revision"] != revision or previous["max_steps"] != max_steps):
        raise ValueError("Resume requires the original model revision and max_steps")
    set_seed(config["seed"])
    precision = config["precision"]
    if precision == "auto":
        precision = (
            ("bfloat16" if torch.cuda.is_bf16_supported() else "float16")
            if device == "cuda"
            else "float32"
        )
    dtype = getattr(torch, precision)
    use_bf16 = precision == "bfloat16"
    quantized = config["load_in_4bit"]
    if config["backend"] == "unsloth":
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=config["model_id"],
            revision=revision,
            max_seq_length=config["max_length"],
            dtype=dtype,
            load_in_4bit=quantized,
            trust_remote_code=False,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=config["lora_r"],
            lora_alpha=config["lora_alpha"],
            target_modules=TARGET_MODULES,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=config["seed"],
        )
        peft_config = None
    else:
        tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=revision)
        quantization = (
            BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=dtype,
            )
            if quantized
            else None
        )
        model = AutoModelForCausalLM.from_pretrained(
            config["model_id"],
            revision=revision,
            dtype=dtype,
            quantization_config=quantization,
            device_map={"": torch.cuda.current_device() if device == "cuda" else "cpu"},
            trust_remote_code=False,
        )
        if quantized:
            model = prepare_model_for_kbit_training(model)
        peft_config = LoraConfig(
            r=config["lora_r"],
            lora_alpha=config["lora_alpha"],
            lora_dropout=0,
            target_modules=TARGET_MODULES,
            bias="none",
            task_type="CAUSAL_LM",
        )
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    model.config.use_cache = False
    train_data = Dataset.from_list(
        training_examples(rows["train"], tokenizer, config["max_length"])
    )
    validation_data = Dataset.from_list(
        training_examples(rows["validation"], tokenizer, config["max_length"])
    )
    args = SFTConfig(
        output_dir=str(output),
        seed=config["seed"],
        data_seed=config["seed"],
        max_length=config["max_length"],
        num_train_epochs=config["epochs"],
        max_steps=max_steps,
        learning_rate=config["learning_rate"],
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        optim="adamw_torch",
        bf16=use_bf16,
        fp16=precision == "float16",
        use_cpu=device == "cpu",
        gradient_checkpointing=config["gradient_checkpointing"],
        completion_only_loss=True,
        packing=False,
        eval_strategy=config["eval_strategy"],
        save_strategy=config["save_strategy"],
        save_steps=config["save_steps"],
        save_total_limit=2,
        logging_steps=config["logging_steps"],
        logging_first_step=True,
        report_to="none",
        dataloader_num_workers=0,
        dataloader_pin_memory=device == "cuda",
    )
    output.mkdir(parents=True, exist_ok=True)

    class ProgressCallback(TrainerCallback):
        def __init__(self):
            self.started = perf_counter()

        def on_log(self, args, state, control, logs=None, **kwargs):
            record = {
                "step": state.global_step,
                "total_steps": state.max_steps,
                "epoch": state.epoch,
                "elapsed_seconds": perf_counter() - self.started,
                **(logs or {}),
            }
            with (output / "progress.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")

    trainer_type = SFTTrainer
    if not config["track_token_metrics"]:
        from aerolm.trainer import LossOnlySFTTrainer

        trainer_type = LossOnlySFTTrainer
    trainer = trainer_type(
        model=model,
        args=args,
        train_dataset=train_data,
        eval_dataset=validation_data,
        processing_class=tokenizer,
        peft_config=peft_config,
        callbacks=[ProgressCallback()],
    )
    output.mkdir(parents=True, exist_ok=True)
    packages = {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}
    run = {
        "domain": "charter",
        "prompt_sha256": hashlib.sha256(
            json.dumps(registry.get("charter").messages(""), sort_keys=True).encode()
        ).hexdigest(),
        "model_id": config["model_id"],
        "model_revision": revision,
        "config": config,
        "config_sha256": sha256(config_path),
        "dataset_manifest": manifest,
        "max_steps": max_steps,
        "resume": resume,
        "python": platform.python_version(),
        "packages": dict(sorted(packages.items())),
        "device": device,
        "precision": precision,
        "cpu_threads": torch.get_num_threads(),
        "processor": platform.processor(),
        "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
        "cuda": torch.version.cuda,
        "status": "running",
        "trainable_parameters": sum(
            p.numel() for p in trainer.model.parameters() if p.requires_grad
        ),
        "total_parameters": sum(p.numel() for p in trainer.model.parameters()),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = output / "run_manifest.json"
    manifest_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    try:
        result = trainer.train(resume_from_checkpoint=resume)
        trainer.save_model(str(output))
        tokenizer.save_pretrained(str(output))
        trainer.save_state()
    except BaseException as error:
        run.update(
            status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            error_type=type(error).__name__,
        )
        manifest_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        raise
    run.update(
        status="completed",
        training_metrics=result.metrics,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    manifest_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    return run
