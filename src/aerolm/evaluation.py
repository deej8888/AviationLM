"""Strict raw JSON and schema checks, micro slot scoring, and auditable predictions."""

import hashlib
import importlib.metadata
import json
import platform
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from aerolm.core import Backend
from aerolm.domains.registry import registry
from aerolm.data.generate import sha256
from aerolm.service import strict_json


def facts(value: dict, path: str = "") -> set[tuple[str, str]]:
    """A non-null scalar is a fact. Nulls/empty lists yield no true negatives."""
    result = set()
    for key, item in value.items():
        if key == "request_type":
            continue  # constant routing discriminator is not an extracted fact
        name = f"{path}.{key}" if path else key
        if isinstance(item, dict):
            result |= facts(item, name)
        elif isinstance(item, list):
            for index, entry in enumerate(item):
                if isinstance(entry, dict):
                    result |= facts(entry, f"{name}[{index}]")
                elif entry is not None:
                    # Requirements are unordered and duplicates do not earn credit.
                    result.add((name, json.dumps(entry, sort_keys=True)))
        elif item is not None:
            result.add((name, json.dumps(item, sort_keys=True)))
    return result


def metrics(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def load_rows(path: Path) -> list[dict]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows:
        raise ValueError("Evaluation data cannot be empty")
    if any(row.get("provenance") != "synthetic" or row.get("license") != "CC0-1.0" for row in rows):
        raise ValueError("This pipeline accepts only declared synthetic CC0 fixtures")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Dataset contains duplicate IDs")
    for row in rows:
        registry.get("charter").schema.model_validate_json(json.dumps(row["expected"]), strict=True)
    return rows


def evaluate(backend: Backend, dataset: Path, output: Path, label: str | None = None) -> dict:
    spec = registry.get("charter")
    rows = load_rows(dataset)
    totals = Counter(tp=0, fp=0, fn=0)
    fields: dict[str, Counter] = {}
    predictions, latencies = [], []
    valid_json = valid_schema = exact = 0
    for row in rows:
        start = perf_counter()
        # Backend/runtime failures stop the run; they are not silently scored as model mistakes.
        raw = backend.generate(row["text"], spec)
        latency = (perf_counter() - start) * 1000
        latencies.append(latency)
        parsed = None
        json_ok = schema_ok = False
        try:
            parsed = strict_json(raw)
            json_ok = True
            parsed = spec.schema.model_validate_json(json.dumps(parsed), strict=True).model_dump(
                mode="json"
            )
            schema_ok = True
        except ValueError:
            pass
        valid_json += json_ok
        valid_schema += schema_ok
        expected = facts(row["expected"])
        predicted = facts(parsed) if schema_ok else set()
        tp, fp, fn = predicted & expected, predicted - expected, expected - predicted
        totals.update(tp=len(tp), fp=len(fp), fn=len(fn))
        exact += schema_ok and predicted == expected
        for key, group in (("tp", tp), ("fp", fp), ("fn", fn)):
            for path, _ in group:
                field = re.sub(r"\[\d+\]", "[]", path)
                fields.setdefault(field, Counter(tp=0, fp=0, fn=0))[key] += 1
        predictions.append(
            {
                "id": row["id"],
                "raw_output": raw,
                "json_valid": json_ok,
                "schema_valid": schema_ok,
                "latency_ms": latency,
                "tp": len(tp),
                "fp": len(fp),
                "fn": len(fn),
            }
        )
    adapter = getattr(backend, "adapter_path", None)
    adapter_hashes = {}
    if adapter:
        for path in sorted(Path(adapter).rglob("*")):
            if path.is_file() and path.suffix in {".json", ".safetensors"}:
                adapter_hashes[str(path.relative_to(adapter))] = sha256(path)
    versions = {}
    for package in ("aerolm", "pydantic", "torch", "transformers", "peft", "trl"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    report = {
        "report_version": "1.0",
        "label": label or backend.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": backend.name,
        "model_id": getattr(backend, "model_id", None),
        "model_revision": getattr(backend, "resolved_revision", None),
        "adapter_loaded": bool(adapter),
        "adapter_hashes": adapter_hashes,
        "dataset": {"name": dataset.name, "sha256": sha256(dataset), "count": len(rows)},
        "prompt_sha256": hashlib.sha256(
            json.dumps(spec.messages(""), sort_keys=True).encode()
        ).hexdigest(),
        "generation": {
            "do_sample": False,
            "enable_thinking": False,
            "max_new_tokens": getattr(getattr(backend, "settings", None), "max_new_tokens", None),
        },
        "metrics": {
            **metrics(**totals),
            "json_validity": valid_json / len(rows),
            "schema_validity": valid_schema / len(rows),
            "exact_match": exact / len(rows),
        },
        "per_field": {name: metrics(**counts) for name, counts in sorted(fields.items())},
        "latency_ms": {
            "median": statistics.median(latencies),
            "mean": statistics.mean(latencies),
            "p95": sorted(latencies)[max(0, int(len(rows) * 0.95) - 1)],
            "includes_model_load": False,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": versions,
        },
        "limitations": [
            "Synthetic evaluation only; not evidence of real-world dispatch accuracy.",
            "Invalid schema outputs receive no slot credit.",
            "No null/empty true-negative credit; leg order is significant.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".predictions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in predictions), encoding="utf-8", newline="\n"
    )
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def compare_reports(baseline: Path, tuned: Path) -> dict:
    base, adapter = (json.loads(path.read_text(encoding="utf-8")) for path in (baseline, tuned))
    for key in ("dataset", "prompt_sha256", "model_id", "model_revision", "generation"):
        if base[key] != adapter[key]:
            raise ValueError(f"Comparison requires identical {key}")
    if base["backend"] != "hf" or adapter["backend"] != "hf":
        raise ValueError("Base vs tuned comparison requires two HF model runs")
    if base["adapter_loaded"] or not adapter["adapter_loaded"]:
        raise ValueError("Expected a base run followed by an adapter run")
    return {
        name: {
            "baseline": base["metrics"][name],
            "fine_tuned": adapter["metrics"][name],
            "delta": adapter["metrics"][name] - base["metrics"][name],
        }
        for name in ("precision", "recall", "f1", "json_validity", "schema_validity", "exact_match")
    }
