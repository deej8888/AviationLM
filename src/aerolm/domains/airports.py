"""Offline advisory lookup of stated airport codes; never infer or rewrite a route."""

import csv
import gzip
import hashlib
import io
import json
from collections import defaultdict
from functools import lru_cache
from importlib.resources import files

from pydantic import BaseModel


@lru_cache(maxsize=1)
def load_reference() -> tuple[dict, dict[str, list[dict]]]:
    folder = files("aerolm.data").joinpath("reference")
    metadata = json.loads(folder.joinpath("airports.manifest.json").read_text(encoding="utf-8"))
    compressed = folder.joinpath("airports.csv.gz").read_bytes()
    if hashlib.sha256(compressed).hexdigest() != metadata["compressed_sha256"]:
        raise ValueError("Airport reference checksum mismatch")
    content = gzip.decompress(compressed)
    if hashlib.sha256(content).hexdigest() != metadata["uncompressed_sha256"]:
        raise ValueError("Airport reference content checksum mismatch")
    index: dict[str, list[dict]] = defaultdict(list)
    for row in csv.DictReader(io.StringIO(content.decode("utf-8"), newline="")):
        index[row["code"]].append(
            {
                k: row[k]
                for k in (
                    "scheme",
                    "name",
                    "municipality",
                    "country",
                    "type",
                    "icao_code",
                    "iata_code",
                )
            }
        )
    if sum(map(len, index.values())) != metadata["record_count"]:
        raise ValueError("Airport reference record count mismatch")
    return metadata, dict(index)


def airport_checks(value: BaseModel, text: str) -> list[dict]:
    del text  # Source mentions are checked separately by the domain's evidence callback.
    data = value.model_dump(mode="json")
    try:
        metadata, index = load_reference()
        source = f"OurAirports {metadata['revision'][:12]}"
        available = True
    except (OSError, ValueError, KeyError, EOFError):
        source, index, available = "OurAirports snapshot unavailable", {}, False
    checks = []
    for i, flight in enumerate(data.get("legs", [])):
        for field in ("origin", "destination"):
            code = flight.get(field)
            if not code:
                continue
            matches = index.get(code, [])
            if not available:
                status, message = (
                    "unavailable",
                    f"Airport reference unavailable; check {code} manually.",
                )
            elif not matches:
                status, message = (
                    "not_found",
                    f"{code} was not found in the airport reference; confirm it.",
                )
            elif len(matches) > 1:
                status, message = (
                    "ambiguous",
                    f"{code} has multiple reference matches; confirm the intended airport.",
                )
            elif matches[0]["type"] == "closed":
                status, message = (
                    "closed",
                    f"{code} is marked closed in the reference; confirm current status.",
                )
            else:
                status, message = "matched", f"{code} appears in the airport reference."
            checks.append(
                {
                    "kind": "airport_reference",
                    "path": f"legs[{i}].{field}",
                    "value": code,
                    "status": status,
                    "message": message,
                    "source": source,
                    "matches": matches[:5],
                    "match_count": len(matches),
                }
            )
    return checks
