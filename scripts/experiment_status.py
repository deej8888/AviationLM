"""Read training/evaluation progress without importing the model or using CPU capacity."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/full-cpu"))
    args = parser.parse_args()
    state_path = args.output / "experiment.json"
    if not state_path.exists():
        print("Experiment has not started")
        return
    state = json.loads(state_path.read_text())
    adapter_path = Path(state.get("training_adapter", args.output / "adapter"))
    progress_path = adapter_path / "progress.jsonl"
    if progress_path.exists():
        records = [
            json.loads(line) for line in progress_path.read_text().splitlines() if line.strip()
        ]
        if records:
            state["training_progress"] = records[-1]
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
