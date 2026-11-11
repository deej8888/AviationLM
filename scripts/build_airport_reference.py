"""Rebuild AeroLM's compact public-domain OurAirports snapshot from a pinned CSV."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
from pathlib import Path

REVISION = "480cb340247e7dfd6c22e31d309895ef003e3d80"
SOURCE_SHA256 = "b311ab030775908769395b6814840f01732b27a5176b85f1a9ed3b5d98ff052b"
SOURCE_URL = (
    f"https://raw.githubusercontent.com/davidmegginson/ourairports-data/{REVISION}/airports.csv"
)


def build(source: Path, target: Path):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source CSV differs from the pinned OurAirports revision")
    records = []
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")):
        for kind, column, pattern in (
            ("iata", "iata_code", r"[A-Z]{3}"),
            ("icao", "icao_code", r"[A-Z]{4}"),
        ):
            code = (row.get(column) or "").strip().upper()
            if re.fullmatch(pattern, code):
                records.append(
                    (
                        code,
                        kind,
                        row["name"],
                        row["municipality"],
                        row["iso_country"],
                        row["type"],
                        row["icao_code"],
                        row["iata_code"],
                    )
                )
    records.sort()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        ["code", "scheme", "name", "municipality", "country", "type", "icao_code", "iata_code"]
    )
    writer.writerows(records)
    content = stream.getvalue().encode("utf-8")
    target.mkdir(parents=True, exist_ok=True)
    compressed = target / "airports.csv.gz"
    with compressed.open("wb") as file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=file, mtime=0) as archive:
            archive.write(content)
    metadata = {
        "source": "OurAirports airports.csv",
        "revision": REVISION,
        "source_url": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "license": "Public domain, per https://ourairports.com/data/",
        "record_count": len(records),
        "transformation": (
            "Extract uppercase alphabetic 3-letter IATA and 4-letter ICAO codes; "
            "retain airport name, municipality, country, type, IATA and ICAO fields; "
            "sorted, UTF-8 CSV, gzip mtime=0."
        ),
        "uncompressed_sha256": hashlib.sha256(content).hexdigest(),
        "compressed_sha256": hashlib.sha256(compressed.read_bytes()).hexdigest(),
        "disclaimer": (
            "Reference snapshot only, without guarantee of accuracy or fitness for use; "
            "not authoritative operational or navigation data."
        ),
    }
    (target / "airports.manifest.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Pinned upstream airports.csv")
    parser.add_argument("--output", type=Path, default=Path("src/aerolm/data/reference"))
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
