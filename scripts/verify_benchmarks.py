"""Recompute committed rules scores; compare metrics, prompts and data, not wall clocks."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from aerolm.backends.rules import RulesBackend
from aerolm.data.generate import generate_dataset
from aerolm.evaluation import evaluate


def main():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        generate_dataset(root / "data")
        for label, dataset in (
            ("rules-generated", root / "data/test.jsonl"),
            ("rules-challenge", Path("data/charter_challenge.jsonl")),
        ):
            report = evaluate(RulesBackend(), dataset, root / f"{label}.json", label)
            committed = json.loads(
                (Path("benchmarks/results") / f"{label}.json").read_text(encoding="utf-8")
            )
            for key in ("dataset", "metrics", "per_field", "prompt_sha256"):
                if report[key] != committed[key]:
                    raise SystemExit(f"Benchmark drift: {label}/{key}; rerun and review results")
            print(
                f"Verified {label}: {report['dataset']['count']} examples, F1={report['metrics']['f1']:.6f}"
            )


if __name__ == "__main__":
    main()
