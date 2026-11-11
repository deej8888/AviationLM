"""Evaluate frozen hand-authored charter cases; preserve raw outputs and progress."""

import argparse
import gc
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from aerolm.backends.huggingface import HuggingFaceBackend
from aerolm.backends.rules import RulesBackend
from aerolm.data.generate import sha256
from aerolm.domains.registry import registry
from aerolm.evaluation import evaluate, load_rows
from aerolm.settings import Settings

DATA = Path("data/charter_independent.jsonl")
MANIFEST = Path("data/charter_independent.manifest.json")
MODEL = "Qwen/Qwen3-0.6B"
REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/independent-benchmark"))
    parser.add_argument("--v1", type=Path, default=Path("artifacts/full-cpu/adapter"))
    parser.add_argument("--v2", type=Path, default=Path("artifacts/robust-v2.1/full/adapter"))
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = load_rows(DATA)
    if sha256(DATA) != manifest["sha256"] or len(rows) != manifest["count"]:
        raise ValueError("Frozen independent benchmark does not match its manifest")
    for adapter in (args.v1, args.v2):
        run = json.loads((adapter / "run_manifest.json").read_text(encoding="utf-8"))
        if (
            run.get("status") != "completed"
            or run["model_id"] != MODEL
            or run["model_revision"] != REVISION
        ):
            raise ValueError(f"Invalid or incompatible completed adapter: {adapter}")
    state = {
        "status": "running",
        "phase": "prepare",
        "pid": os.getpid(),
        "dataset_sha256": manifest["sha256"],
        "total": len(rows),
        "started_at": datetime.now(UTC).isoformat(),
    }

    def phase(name, **kwargs):
        state.update(phase=name, updated_at=datetime.now(UTC).isoformat(), **kwargs)
        write_json(args.output / "progress.json", state)
        print(json.dumps(state), flush=True)

    try:
        modes = [
            ("rules", None, False),
            ("base-raw", None, False),
            ("base-fewshot-constrained", None, True),
            ("v1-raw", args.v1, False),
            ("v2-raw", args.v2, False),
        ]
        summary = {}
        for name, adapter, enhanced in modes:
            path = args.output / f"{name}.json"
            phase(f"load_{name}", evaluated=0)
            if name == "rules":
                engine = RulesBackend()
                prompt = registry.get("charter").messages("")
                expected_generation = {
                    "do_sample": False,
                    "enable_thinking": False,
                    "max_new_tokens": None,
                }
                expected_inference = {"device": "cpu", "precision": None, "cpu_threads": None}
            else:
                settings = Settings(
                    backend="hf",
                    model_id=MODEL,
                    model_revision=REVISION,
                    adapter_path=str(adapter) if adapter else None,
                    device="cpu",
                    precision="bfloat16",
                    cpu_threads=12,
                    few_shot_path="data/charter_demonstrations.jsonl" if enhanced else None,
                    structured_output=enhanced,
                    max_new_tokens=1024,
                    max_input_tokens=4096,
                )
                engine = HuggingFaceBackend(settings)
                prompt = engine.messages(registry.get("charter"), "")
                expected_generation = {
                    "do_sample": False,
                    "enable_thinking": False,
                    "max_new_tokens": 1024,
                }
                if enhanced:
                    expected_generation["structured_output"] = "lm-format-enforcer-0.11.3"
                expected_inference = {"device": "cpu", "precision": "bfloat16", "cpu_threads": 12}
            prompt_sha = hashlib.sha256(json.dumps(prompt, sort_keys=True).encode()).hexdigest()
            prior = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if prior and (
                prior["dataset"]["sha256"] == manifest["sha256"]
                and prior["prompt_sha256"] == prompt_sha
                and prior["generation"] == expected_generation
                and prior["inference"] == expected_inference
                and prior["adapter_loaded"] == bool(adapter)
                and prior["backend"] == engine.name
                and (
                    name == "rules"
                    or (prior["model_id"] == MODEL and prior["model_revision"] == REVISION)
                )
                and (
                    not adapter
                    or all(
                        prior["adapter_hashes"].get(f) == sha256(adapter / f)
                        for f in (
                            "adapter_model.safetensors",
                            "adapter_config.json",
                            "run_manifest.json",
                        )
                    )
                )
            ):
                report = prior
                phase(f"reuse_{name}")
            else:
                report = evaluate(
                    engine,
                    DATA,
                    path,
                    f"independent-{name}",
                    on_progress=lambda i, n, sample, name=name: phase(
                        f"evaluate_{name}", evaluated=i
                    ),
                )
            summary[name] = {"metrics": report["metrics"], "diagnostics": report["diagnostics"]}
            del engine
            gc.collect()
        write_json(args.output / "summary.json", summary)
        phase("completed", status="completed", completed_at=datetime.now(UTC).isoformat())
    except BaseException as error:
        phase("failed", status="failed", error_type=type(error).__name__, error=str(error))
        raise


if __name__ == "__main__":
    main()
