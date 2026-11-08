import json

import pytest

from aerolm.backends.rules import RulesBackend
from aerolm.data.generate import generate_dataset
from aerolm.evaluation import compare_reports, evaluate, facts, metrics


def test_wrong_value_is_both_false_positive_and_false_negative():
    expected = facts(
        {"passengers": 6, "budget": None, "special_requirements": ["wifi", "catering"]}
    )
    predicted = facts(
        {"passengers": 8, "budget": None, "special_requirements": ["catering", "wifi"]}
    )
    assert len(expected & predicted) == 2
    assert len(expected - predicted) == 1
    assert len(predicted - expected) == 1
    assert facts({"request_type": "charter", "legs": [], "passengers": None}) == set()
    assert metrics(2, 1, 1)["f1"] == pytest.approx(2 / 3)


def test_invalid_output_gets_no_slot_credit(tmp_path):
    generate_dataset(tmp_path, train=1, validation=1, test=1)

    class InvalidBackend:
        name = "invalid"

        def generate(self, text, domain):
            return '{"passengers":"6"}'

    report = evaluate(InvalidBackend(), tmp_path / "test.jsonl", tmp_path / "report.json")
    assert report["metrics"]["json_validity"] == 1
    assert report["metrics"]["schema_validity"] == 0
    assert report["metrics"]["recall"] == 0
    assert report["metrics"]["fn"] > 0
    assert (tmp_path / "report.predictions.jsonl").is_file()


def test_report_auditability_and_no_rules_to_tuned_comparison(tmp_path):
    generate_dataset(tmp_path, train=5, validation=5, test=5)
    report = evaluate(RulesBackend(), tmp_path / "test.jsonl", tmp_path / "rules.json")
    assert report["dataset"]["count"] == 5
    assert len(report["dataset"]["sha256"]) == 64
    assert not report["adapter_loaded"] and report["model_id"] is None
    assert report["metrics"]["schema_validity"] == 1
    with pytest.raises(ValueError, match="HF model runs"):
        compare_reports(tmp_path / "rules.json", tmp_path / "rules.json")


def test_compare_refuses_different_test_sets(tmp_path):
    base = {
        "dataset": {"sha256": "a"},
        "prompt_sha256": "p",
        "model_id": "qwen",
        "model_revision": "sha",
        "generation": {},
    }
    (tmp_path / "base.json").write_text(json.dumps(base))
    (tmp_path / "tuned.json").write_text(json.dumps({**base, "dataset": {"sha256": "b"}}))
    with pytest.raises(ValueError, match="identical dataset"):
        compare_reports(tmp_path / "base.json", tmp_path / "tuned.json")
