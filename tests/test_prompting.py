import json

import pytest

from aerolm.domains.registry import registry
from aerolm.prompting import load_demonstrations, with_demonstrations


def test_demonstrations_are_included_in_actual_prompt_and_preserve_nulls(tmp_path):
    path = tmp_path / "demos.jsonl"
    row = {
        "text": "Six passengers.",
        "expected": {"passengers": 6},
        "provenance": "synthetic",
        "license": "CC0-1.0",
    }
    path.write_text(json.dumps(row) + "\n")
    domain = registry.get("charter")
    messages = with_demonstrations(domain, "New request", load_demonstrations(path, domain))
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == '{"passengers":6}'
    assert messages[-1]["content"] == "New request"
    path.write_text(json.dumps({**row, "provenance": "private inbox"}))
    with pytest.raises(ValueError, match="provenance"):
        load_demonstrations(path, domain)
