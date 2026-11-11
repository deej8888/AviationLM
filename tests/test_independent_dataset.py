import json
import runpy
from pathlib import Path

from aerolm.data.generate import sha256
from aerolm.data.robust import generate_robust_split
from aerolm.domains.charter import CharterRequest
from aerolm.evaluation import load_rows


def test_hand_authored_benchmark_is_frozen_and_excluded_from_generated_sets():
    path = Path("data/charter_independent.jsonl")
    manifest = json.loads(Path("data/charter_independent.manifest.json").read_text())
    rows = load_rows(path)
    assert len(rows) == manifest["count"] == 50
    assert sha256(path) == manifest["sha256"]
    assert manifest["independent_human_reviewed"] is False
    assert len({r["text"] for r in rows}) == len(rows)
    assert all(r["split"] == "test" and r["provenance"] == "synthetic" for r in rows)
    generated = {
        r["text"]
        for split, n in (("train", 2000), ("validation", 200), ("test", 300))
        for r in generate_robust_split(split, n, 84)
    }
    assert not generated.intersection(r["text"] for r in rows)


def test_published_labels_match_the_hand_authored_source():
    module = runpy.run_path("scripts/create_independent_benchmark.py")
    rows = load_rows(Path("data/charter_independent.jsonl"))
    for row, (tag, text, expected) in zip(rows, module["CASES"], strict=True):
        assert row["id"] == f"independent-{tag}" and row["text"] == text
        assert row["expected"] == CharterRequest(**expected).model_dump(mode="json")
