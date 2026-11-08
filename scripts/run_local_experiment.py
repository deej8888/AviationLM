"""Train and evaluate a full local experiment, with durable progress and no cloud costs.

Run from the repository root with the ML environment. Interrupted runs can be
restarted with the same command; matching completed phases are reused.
"""

import argparse
import gc
import hashlib
import json
import os
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from aerolm.backends.huggingface import HuggingFaceBackend
from aerolm.data.generate import generate_dataset, sha256
from aerolm.domains.registry import registry
from aerolm.evaluation import compare_reports, evaluate
from aerolm.examples import EXAMPLES
from aerolm.service import ExtractionService
from aerolm.settings import Settings
from aerolm.training import TrainingConfig, load_training_data, train


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/cpu-lora.toml"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/full-cpu"))
    parser.add_argument(
        "--activate", action="store_true", help="Activate locally after a valid demo extraction"
    )
    args = parser.parse_args()
    config = TrainingConfig.model_validate(tomllib.loads(args.config.read_text())).model_dump()
    root, data_dir = args.output, args.output / "data"
    adapter_dir = root / "adapter"
    state = {
        "status": "running",
        "phase": "data",
        "pid": os.getpid(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    }

    def phase(name: str, **extra):
        state.update(phase=name, updated_at=datetime.now(timezone.utc).isoformat(), **extra)
        write_json(root / "experiment.json", state)
        print(f"PHASE {name}: {json.dumps(extra)}", flush=True)

    try:
        if not (data_dir / "manifest.json").exists():
            generate_dataset(data_dir, seed=config["seed"], train=1000, validation=120, test=120)
        manifest, _ = load_training_data(data_dir)
        if any(
            manifest["splits"][key]["count"] != count
            for key, count in (("train", 1000), ("validation", 120), ("test", 120))
        ):
            raise ValueError("Full experiment requires 1000/120/120 splits")
        for split in ("train", "validation", "test"):
            if sha256(data_dir / f"{split}.jsonl") != manifest["splits"][split]["sha256"]:
                raise ValueError(f"Dataset manifest mismatch: {split}")
        prior_path = adapter_dir / "run_manifest.json"
        prior = json.loads(prior_path.read_text()) if prior_path.exists() else None
        if prior and (
            prior["config_sha256"] != sha256(args.config) or prior["dataset_manifest"] != manifest
        ):
            raise ValueError("Existing experiment uses a different config or dataset")
        if not prior or prior["status"] != "completed":
            checkpoints = sorted(
                adapter_dir.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1])
            )
            resume = str(checkpoints[-1]) if checkpoints else None
            if prior and not resume:
                raise ValueError(
                    "Interrupted run has no checkpoint; choose a fresh --output directory"
                )
            phase("training", resume=resume)
            train(args.config, data_dir, adapter_dir, resume=resume)
        gc.collect()
        spec = registry.get("charter")
        prompt_hash = hashlib.sha256(
            json.dumps(spec.messages(""), sort_keys=True).encode()
        ).hexdigest()
        common = dict(
            backend="hf",
            model_id=config["model_id"],
            model_revision=config["revision"],
            device=config["device"],
            precision=config["precision"],
            cpu_threads=config["cpu_threads"],
            max_new_tokens=1024,
            max_input_tokens=4096,
        )
        datasets = [
            ("generated", data_dir / "test.jsonl"),
            ("challenge", Path("data/charter_challenge.jsonl")),
        ]
        report_paths = {}
        for mode in ("base", "tuned"):
            engine = None
            for suite, dataset in datasets:
                report_path = Path("benchmarks/results") / f"qwen-{mode}-{suite}.json"
                report_paths[mode, suite] = report_path
                existing = json.loads(report_path.read_text()) if report_path.exists() else None
                expected_adapter = mode == "tuned"
                if existing and (
                    existing["dataset"]["sha256"] == sha256(dataset)
                    and existing["prompt_sha256"] == prompt_hash
                    and existing["model_revision"] == config["revision"]
                    and existing["model_id"] == config["model_id"]
                    and existing["adapter_loaded"] == expected_adapter
                    and existing["generation"]
                    == {"do_sample": False, "enable_thinking": False, "max_new_tokens": 1024}
                    and existing.get("inference")
                    == {
                        "device": config["device"],
                        "precision": config["precision"],
                        "cpu_threads": config["cpu_threads"],
                    }
                    and (
                        not expected_adapter
                        or existing.get("adapter_hashes", {}).get("adapter_model.safetensors")
                        == sha256(adapter_dir / "adapter_model.safetensors")
                    )
                ):
                    phase(f"reuse_{mode}_{suite}")
                    continue
                phase(f"evaluate_{mode}_{suite}")
                if engine is None:
                    engine = HuggingFaceBackend(
                        Settings(
                            **common, adapter_path=str(adapter_dir) if expected_adapter else None
                        )
                    )

                def progress(index, total, sample):
                    phase(f"evaluate_{mode}_{suite}", evaluated=index, total=total)
                    print(
                        f"[{index}/{total}] {sample['id']} schema_valid={sample['schema_valid']}",
                        flush=True,
                    )

                evaluate(
                    engine, dataset, report_path, f"qwen3-0.6b-{mode}-{suite}", on_progress=progress
                )
            if engine is not None:
                del engine
            gc.collect()
        comparisons = {}
        for suite, _ in datasets:
            comparisons[suite] = compare_reports(
                report_paths["base", suite], report_paths["tuned", suite]
            )
        write_json(root / "comparison.json", comparisons)
        if args.activate:
            phase("activate")
            engine = HuggingFaceBackend(Settings(**common, adapter_path=str(adapter_dir)))
            demo = ExtractionService(engine).extract(EXAMPLES[0]["text"])
            write_json(root / "demo-extraction.json", demo.model_dump())
            from dotenv import set_key

            for key, value in {
                "AEROLM_BACKEND": "hf",
                "AEROLM_MODEL_ID": config["model_id"],
                "AEROLM_MODEL_REVISION": config["revision"],
                "AEROLM_ADAPTER_PATH": str(adapter_dir),
                "AEROLM_DEVICE": config["device"],
                "AEROLM_PRECISION": config["precision"],
                "AEROLM_CPU_THREADS": str(config["cpu_threads"]),
            }.items():
                set_key(".env", key, value)
        phase(
            "completed",
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            comparison=str(root / "comparison.json"),
        )
    except BaseException as error:
        phase(
            "interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            status="failed",
            error_type=type(error).__name__,
            error=str(error),
        )
        raise


if __name__ == "__main__":
    main()
