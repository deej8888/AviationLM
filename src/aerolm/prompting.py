"""Auditable prompt demonstrations, independent of model loading."""

import json
from pathlib import Path

from aerolm.core import DomainSpec


def load_demonstrations(path: Path, domain: DomainSpec) -> list[dict]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not 1 <= len(rows) <= 8:
        raise ValueError("Use 1-8 reviewed synthetic demonstrations")
    for row in rows:
        if row.get("provenance") != "synthetic" or row.get("license") != "CC0-1.0":
            raise ValueError("Demonstrations require synthetic CC0 provenance")
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError("Demonstrations require nonempty text")
        domain.schema.model_validate_json(json.dumps(row["expected"]), strict=True)
    return rows


def with_demonstrations(domain: DomainSpec, text: str, rows: list[dict]) -> list[dict]:
    messages = domain.messages(text)
    additions = []
    for row in rows:
        additions.extend(
            [
                {"role": "user", "content": row["text"]},
                {
                    "role": "assistant",
                    "content": json.dumps(row["expected"], separators=(",", ":")),
                },
            ]
        )
    return [messages[0], *additions, *messages[1:]]
