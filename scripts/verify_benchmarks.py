"""Recompute rules and audit every committed model report from raw predictions.

No model loading, network, ML dependencies, or fabricated inference rerun. Replaying
saved outputs verifies scoring arithmetic, not the reproducibility of model generation.
"""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from aerolm.backends.rules import RulesBackend
from aerolm.data.generate import generate_dataset, sha256
from aerolm.data.robust import generate_robust_split
from aerolm.domains.registry import registry
from aerolm.evaluation import evaluate, load_rows
from aerolm.prompting import load_demonstrations, with_demonstrations


class Replay:
    name = "stored-predictions"

    def __init__(self, predictions, demonstrations):
        self.predictions = iter(predictions)
        self.demonstrations = demonstrations

    def generate(self, text, domain):
        return next(self.predictions)["raw_output"]

    def messages(self, domain, text):
        return with_demonstrations(domain, text, self.demonstrations)


def main():
    directory = Path("benchmarks/results")
    with TemporaryDirectory() as temp:
        root = Path(temp)
        generate_dataset(root / "data")
        datasets = [root / "data/test.jsonl", Path("data/charter_challenge.jsonl")]
        pilot_manifest = Path("benchmarks/runs/v2-pilot-training.json")
        if pilot_manifest.exists():
            manifest = json.loads(pilot_manifest.read_text(encoding="utf-8"))["dataset_manifest"]
            dataset = root / "validation.jsonl"
            rows = generate_robust_split(
                "validation", manifest["splits"]["validation"]["count"], manifest["seed"]
            )
            dataset.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                encoding="utf-8",
                newline="\n",
            )
            if sha256(dataset) != manifest["splits"]["validation"]["sha256"]:
                raise SystemExit("Version-2 generator differs from the frozen pilot dataset")
            datasets.append(dataset)
        by_hash = {sha256(p): p for p in datasets}
        domain = registry.get("charter")
        demonstrations = load_demonstrations(Path("data/charter_demonstrations.jsonl"), domain)
        prompt_options = {
            hashlib.sha256(
                json.dumps(with_demonstrations(domain, "", examples), sort_keys=True).encode()
            ).hexdigest(): examples
            for examples in ([], demonstrations)
        }
        for path in sorted(directory.glob("*.json")):
            committed = json.loads(path.read_text(encoding="utf-8"))
            dataset = by_hash.get(committed["dataset"]["sha256"])
            if dataset is None:
                raise SystemExit(
                    f"Unknown benchmark dataset: {path.name}; add its reproducible source"
                )
            rows = load_rows(dataset)
            predictions = [
                json.loads(line)
                for line in path.with_suffix(".predictions.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            if [p["id"] for p in predictions] != [r["id"] for r in rows]:
                raise SystemExit(f"Prediction IDs/order differ from dataset: {path.name}")
            if committed["prompt_sha256"] not in prompt_options:
                raise SystemExit(f"Unknown historical prompt: {path.name}; retain its source")
            backend = (
                RulesBackend()
                if committed["backend"] == "rules"
                else Replay(predictions, prompt_options[committed["prompt_sha256"]])
            )
            report = evaluate(backend, dataset, root / path.name, committed["label"])
            keys = ["dataset", "metrics", "per_field", "prompt_sha256"]
            keys += [key for key in ("diagnostics", "scenarios") if key in committed]
            for key in keys:
                if report[key] != committed[key]:
                    raise SystemExit(f"Benchmark drift: {path.name}/{key}")
            replayed = [
                json.loads(line)
                for line in (root / path.name)
                .with_suffix(".predictions.jsonl")
                .read_text()
                .splitlines()
            ]
            for original, fresh in zip(predictions, replayed, strict=True):
                for key in ("json_valid", "schema_valid", "tp", "fp", "fn"):
                    if original[key] != fresh[key]:
                        raise SystemExit(f"Prediction drift: {path.name}/{original['id']}/{key}")
            method = (
                "regenerated rules" if committed["backend"] == "rules" else "replayed raw outputs"
            )
            print(
                f"Verified {path.stem}: {len(rows)} requests; {method}; "
                f"F1={report['metrics']['f1']:.6f}"
            )


if __name__ == "__main__":
    main()
