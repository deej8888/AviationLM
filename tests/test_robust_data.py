import copy

import pytest

from aerolm.data.robust import (
    coverage,
    generate_robust_dataset,
    generate_robust_split,
    validate_ledger,
)
from aerolm.training import load_training_data


def test_v2_is_reproducible_and_covers_previously_always_present_fields(tmp_path):
    first = generate_robust_dataset(tmp_path / "a", train=100, validation=30, test=30)
    second = generate_robust_dataset(tmp_path / "b", train=100, validation=30, test=30)
    assert first == second
    manifest, rows = load_training_data(tmp_path / "a")
    observed = coverage(rows["train"])
    for field in ("contact_email", "trip_type", "aircraft_preference", "passengers"):
        assert observed["missing_fields"][field] >= 10
    for field in ("destination", "departure_time", "time_zone"):
        assert observed["missing_leg_fields"][field] >= 5
    assert observed["multi_leg_requests"] == 10
    assert observed["empty_requests"] == 10
    assert manifest["generator_version"] == "2.0"
    with pytest.raises(ValueError, match="overwrite"):
        generate_robust_dataset(tmp_path / "a")


def test_v2_labels_follow_corrections_negation_and_omissions():
    rows = generate_robust_split("train", 100, 84)
    for row in rows:
        value, scenario = row["expected"], row["scenario"]
        if scenario == "correction":
            assert "Correction:" in row["text"]
            quoted = next(e["quote"] for e in row["evidence"] if e["path"] == "passengers")
            assert quoted.startswith("Previous message:") and "passenger count is now" in quoted
        if scenario == "negation":
            assert value["special_requirements"] == ["wifi"]
        if scenario == "ambiguous":
            assert value["legs"][0]["departure_date"] is None
            assert value["legs"][0]["departure_time"] is None
        if scenario == "unknown_aircraft":
            assert value["aircraft_preference"].startswith("ExampleAir ")
            assert value["aircraft_category"] is None
        if scenario == "multi_leg":
            assert value["trip_type"] == "multi_leg"
            assert len(value["legs"]) in (2, 3)
            for i, leg in enumerate(value["legs"]):
                assert f"Leg {i + 1}:" in row["text"]
                if i:
                    assert leg["origin"] == value["legs"][i - 1]["destination"]
        for e in row["evidence"]:
            assert e["quote"] in row["text"]


def test_gold_ledger_rejects_unsupported_label_and_missing_source():
    row = generate_robust_split("train", 1, 84)[0]
    changed = copy.deepcopy(row)
    changed["expected"]["contact_email"] = "invented@fiction.example"
    with pytest.raises(ValueError, match="evidence mismatch"):
        validate_ledger(changed)
    changed = copy.deepcopy(row)
    changed["evidence"][0]["quote"] = "this quote never occurs"
    with pytest.raises(ValueError, match="evidence mismatch"):
        validate_ledger(changed)


def test_v2_split_families_and_text_are_disjoint():
    groups = [generate_robust_split(s, 60, 84) for s in ("train", "validation", "test")]
    for i, first in enumerate(groups):
        for second in groups[i + 1 :]:
            assert not {r["text"] for r in first} & {r["text"] for r in second}
            assert not {r["template_family"] for r in first} & {
                r["template_family"] for r in second
            }
