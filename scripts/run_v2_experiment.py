"""Prepare -> validation pilot -> full validation -> frozen test, without overwriting v1.

No cloud resources or automatic activation. The pilot never evaluates test.jsonl.
Completed matching reports are reusable. Select settings using validation only.
"""

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from aerolm.backends.rules import RulesBackend
from aerolm.data.generate import sha256
from aerolm.data.robust import generate_robust_dataset
from aerolm.domains.registry import registry
from aerolm.evaluation import compare_reports, evaluate
from aerolm.settings import Settings
from aerolm.training import TrainingConfig, load_training_data, train


def acquire_lock(root: Path):
    """OS advisory lock is automatically released on process exit, including crashes."""
    root.mkdir(parents=True, exist_ok=True)
    stream = (root / "experiment.lock").open("a+b")
    if stream.tell() == 0:
        stream.write(b"0")
        stream.flush()
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        stream.close()
        raise RuntimeError("Another experiment owns this output directory") from error
    return stream


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def ensure_data(path: Path, counts: tuple[int, int, int], seed: int) -> dict:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        generate_robust_dataset(path, seed, *counts)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("generator_version") != "2.0" or manifest["seed"] != seed:
        raise ValueError("Existing v2 data uses a different generator or seed")
    for split, count in zip(("train", "validation", "test"), counts, strict=True):
        if manifest["splits"][split]["count"] != count:
            raise ValueError("Existing v2 data uses different split sizes")
        if sha256(path / f"{split}.jsonl") != manifest["splits"][split]["sha256"]:
            raise ValueError(f"Dataset hash mismatch: {split}")
    return manifest


def train_or_resume(config_path: Path, data: Path, adapter: Path):
    prior = adapter / "run_manifest.json"
    manifest, _ = load_training_data(data)
    if prior.exists():
        run = json.loads(prior.read_text(encoding="utf-8"))
        if run["config_sha256"] != sha256(config_path) or run["dataset_manifest"] != manifest:
            raise ValueError("Existing adapter belongs to another config or dataset")
        if run["status"] == "completed":
            return
        checkpoints = sorted(adapter.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1]))
        if not checkpoints:
            raise ValueError("Interrupted training has no checkpoint; use a new output directory")
        train(config_path, data, adapter, resume=str(checkpoints[-1]))
    else:
        train(config_path, data, adapter)
    gc.collect()


def verify_selection(selection: dict, config: Path, data_manifest: Path, adapter: Path):
    for expected, path in (
        (selection["config_sha256"], config),
        (selection["data_manifest_sha256"], data_manifest),
        (selection["adapter_sha256"], adapter / "adapter_model.safetensors"),
    ):
        if sha256(path) != expected:
            raise ValueError("Selection changed after freezing; rerun full validation")
    for path, digest in selection["validation_reports"].items():
        if sha256(Path(path)) != digest:
            raise ValueError("Frozen validation report changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["prepare", "pilot", "full", "test"], default="prepare")
    parser.add_argument("--output", type=Path, default=Path("artifacts/robust-v2"))
    parser.add_argument("--config", type=Path, default=Path("configs/cpu-lora-v2.toml"))
    parser.add_argument("--previous-adapter", type=Path, default=Path("artifacts/full-cpu/adapter"))
    args = parser.parse_args()
    config = TrainingConfig.model_validate(tomllib.loads(args.config.read_text())).model_dump()
    root = args.output
    lock = acquire_lock(root)
    state = {
        "status": "running",
        "phase": "prepare",
        "stage": args.stage,
        "pid": os.getpid(),
        "started_at": datetime.now(UTC).isoformat(),
    }

    def phase(name, **extra):
        state.update(phase=name, updated_at=datetime.now(UTC).isoformat(), **extra)
        write_json(root / "experiment.json", state)
        print(json.dumps(state), flush=True)

    try:
        phase("prepare")
        ensure_data(root / "data", (2000, 200, 300), config["seed"])
        if args.stage == "prepare":
            phase(
                "completed",
                status="completed",
                note="Data prepared; no model training or test scoring.",
            )
            return
        if importlib.util.find_spec("lmformatenforcer") is None:
            raise RuntimeError("Install dependencies first: uv sync --extra ml --extra structured")
        pilot = args.stage == "pilot"
        workspace = root / "pilot" if pilot else root / "full"
        data = root / "pilot/data" if pilot else root / "data"
        config_path = args.config
        if pilot:
            ensure_data(data, (240, 24, 1), config["seed"])
            config_path = workspace / "config.toml"
            pilot_text = re.sub(r"(?m)^epochs\s*=.*$", "epochs = 1", args.config.read_text())
            if config_path.exists() and config_path.read_text() != pilot_text:
                raise ValueError("Pilot config changed; choose a new output directory")
            config_path.write_text(pilot_text, encoding="utf-8")
        adapter = workspace / "adapter"
        selection_path = root / "selection.json"
        if args.stage == "test":
            if not selection_path.exists():
                raise ValueError(
                    "Complete full validation and freeze selection before test scoring"
                )
            verify_selection(
                json.loads(selection_path.read_text()),
                args.config,
                root / "data/manifest.json",
                adapter,
            )
        else:
            phase("training", training_adapter=str(adapter))
            train_or_resume(config_path, data, adapter)
        dataset = root / "data/test.jsonl" if args.stage == "test" else data / "validation.jsonl"
        report_dir = workspace / ("test-reports" if args.stage == "test" else "validation-reports")
        phase("evaluate_rules")
        reports = {"rules": report_dir / "rules.json"}
        evaluate(RulesBackend(), dataset, reports["rules"], f"v2-{args.stage}-rules")
        # Each model variant gets its own report; constrained/few-shot is never called a LoRA gain.
        modes = [("base-raw", None, False), ("v2-raw", adapter, False)]
        if args.stage != "test":
            modes.insert(1, ("base-fewshot-constrained", None, True))
            if (args.previous_adapter / "run_manifest.json").exists():
                modes.append(("v1-raw", args.previous_adapter, False))
        from aerolm.backends.huggingface import HuggingFaceBackend

        for name, adapter_path, enhanced in modes:
            output = report_dir / f"{name}.json"
            reports[name] = output
            settings = Settings(
                backend="hf",
                model_id=config["model_id"],
                model_revision=config["revision"],
                device=config["device"],
                precision=config["precision"],
                cpu_threads=config["cpu_threads"],
                adapter_path=str(adapter_path) if adapter_path else None,
                few_shot_path="data/charter_demonstrations.jsonl" if enhanced else None,
                structured_output=enhanced,
                max_new_tokens=1024,
                max_input_tokens=4096,
            )
            phase(f"load_{name}", evaluated=0)
            engine = HuggingFaceBackend(settings)
            prompt_hash = hashlib.sha256(
                json.dumps(engine.messages(registry.get("charter"), ""), sort_keys=True).encode()
            ).hexdigest()
            generation = {"do_sample": False, "enable_thinking": False, "max_new_tokens": 1024}
            if enhanced:
                generation["structured_output"] = "lm-format-enforcer-0.11.3"
            previous = json.loads(output.read_text()) if output.exists() else None
            if previous and (
                previous["dataset"]["sha256"] == sha256(dataset)
                and previous["prompt_sha256"] == prompt_hash
                and previous["model_id"] == config["model_id"]
                and previous["model_revision"] == config["revision"]
                and previous["generation"] == generation
                and previous["inference"]
                == {
                    "device": config["device"],
                    "precision": config["precision"],
                    "cpu_threads": config["cpu_threads"],
                }
                and previous["adapter_loaded"] == bool(adapter_path)
                and (
                    not adapter_path
                    or previous["adapter_hashes"]["adapter_model.safetensors"]
                    == sha256(adapter_path / "adapter_model.safetensors")
                )
            ):
                phase(f"reuse_{name}")
            else:
                evaluate(
                    engine,
                    dataset,
                    output,
                    f"v2-{args.stage}-{name}",
                    on_progress=lambda i, n, sample, name=name: phase(
                        f"evaluate_{name}", evaluated=i, total=n
                    ),
                )
            del engine
            gc.collect()
        comparison = compare_reports(reports["base-raw"], reports["v2-raw"])
        write_json(workspace / f"{args.stage}-comparison.json", comparison)
        summary = {}
        for name, path in reports.items():
            report = json.loads(path.read_text())
            summary[name] = {"metrics": report["metrics"], "diagnostics": report["diagnostics"]}
        write_json(workspace / f"{args.stage}-summary.json", summary)
        if args.stage == "full":
            write_json(
                selection_path,
                {
                    "frozen_at": datetime.now(UTC).isoformat(),
                    "config_sha256": sha256(args.config),
                    "data_manifest_sha256": sha256(root / "data/manifest.json"),
                    "adapter_sha256": sha256(adapter / "adapter_model.safetensors"),
                    "validation_reports": {str(p): sha256(p) for p in reports.values()},
                    "note": (
                        "Frozen experiment candidate, not a production qualification. "
                        "Test was not scored."
                    ),
                },
            )
        phase(
            "completed", status="completed", summary=str(workspace / f"{args.stage}-summary.json")
        )
    except BaseException as error:
        phase("failed", status="failed", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        lock.close()


if __name__ == "__main__":
    main()
