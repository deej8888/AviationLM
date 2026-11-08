import json

from aerolm.data.generate import generate_dataset, generate_split
from aerolm.domains.charter import CharterRequest


def test_reproducible_and_disjoint(tmp_path):
    first = generate_dataset(tmp_path / "a", train=40, validation=20, test=20)
    second = generate_dataset(tmp_path / "b", train=40, validation=20, test=20)
    assert first == second
    text_sets, family_sets = [], []
    for split in ("train", "validation", "test"):
        rows = [
            json.loads(line)
            for line in (tmp_path / "a" / f"{split}.jsonl").read_text().splitlines()
        ]
        text_sets.append({row["text"] for row in rows})
        family_sets.append({row["template_family"] for row in rows})
        for row in rows:
            CharterRequest.model_validate_json(json.dumps(row["expected"]), strict=True)
            assert row["provenance"] == "synthetic" and row["license"] == "CC0-1.0"
    for sets in (text_sets, family_sets):
        assert not sets[0] & sets[1] and not sets[0] & sets[2] and not sets[1] & sets[2]


def test_generator_abstention_labels_are_independent():
    rows = generate_split("train", 40, 42)
    for index, row in enumerate(rows):
        if index % 10 == 0:
            assert row["expected"]["legs"][0]["departure_date"] is None
            assert "next Friday" in row["text"]
        if index % 13 == 0:
            assert row["expected"]["passengers"] is None
            assert "passenger count TBD" in row["text"]
        if index % 17 == 0:
            assert row["expected"]["legs"][0]["origin"] is None
            assert "London" in row["text"]
