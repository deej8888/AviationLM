"""Conservative source-mention checks, separate from raw extraction and scoring.

A match establishes textual support for a candidate, not correct role assignment,
negation handling, or factual truth. Unrecognized wording stays unverified.
"""

import re

from pydantic import BaseModel

from aerolm.backends.rules import AIRCRAFT, DATE, parse_date, parse_time

NUMBER_WORDS = {
    word: index
    for index, word in enumerate(
        (
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        )
    )
}


def source_evidence(value: BaseModel, text: str) -> list[dict]:
    data = value.model_dump(mode="json")
    evidence = []

    def add(path, candidate, match=None, method="exact_mention"):
        if candidate is None:
            return
        evidence.append(
            {
                "path": path,
                "value": candidate,
                "status": "matched" if match else "unverified",
                "quote": match[0] if match else None,
                "start": match.start() if match else None,
                "end": match.end() if match else None,
                "method": method,
            }
        )

    def literal(candidate):
        return re.search(r"(?<!\w)" + re.escape(str(candidate)) + r"(?!\w)", text, re.I)

    times = list(
        re.finditer(
            r"\b(?:[01]?\d|2[0-3]):[0-5]\d\s*(?:am|pm)?\s*(?:Z|Zulu|UTC|local)?\b"
            r"|\b(?:[01]\d|2[0-3])[0-5]\d\s*(?:Z|Zulu|UTC)\b",
            text,
            re.I,
        )
    )
    dates = list(DATE.finditer(text))
    for i, leg in enumerate(data["legs"]):
        for field, candidate in leg.items():
            if candidate is None:
                continue
            method = "exact_mention"
            if field == "departure_date":
                match = next((m for m in dates if str(parse_date(m[0])) == candidate), None)
                method = "date_normalization"
            elif field == "departure_time":
                match = next((m for m in times if parse_time(m[0])[0] == candidate), None)
                method = "time_normalization"
            elif field == "time_zone":
                match = next((m for m in times if parse_time(m[0])[1] == candidate), None)
                method = "time_normalization"
            else:
                match = literal(candidate)
            add(f"legs[{i}].{field}", candidate, match, method)
    pax = list(
        re.finditer(
            r"\b(\d{1,4}|" + "|".join(NUMBER_WORDS) + r")\s+(?:pax|passengers?|people|guests?)\b",
            text,
            re.I,
        )
    )
    matches = [
        m
        for m in pax
        if (int(m[1]) if m[1].isdigit() else NUMBER_WORDS[m[1].lower()]) == data["passengers"]
    ]
    add("passengers", data["passengers"], matches[0] if matches else None, "passenger_mention")
    trip_patterns = {
        "one_way": r"\bone[ -]way\b",
        "round_trip": r"\bround[ -]trip\b",
        "multi_leg": r"\bmulti[ -]leg\b",
    }
    trip = data["trip_type"]
    add("trip_type", trip, re.search(trip_patterns[trip], text, re.I) if trip else None)
    for field in ("aircraft_preference", "budget", "contact_email"):
        candidate = data[field]
        add(field, candidate, literal(candidate) if candidate is not None else None)
    category = data["aircraft_category"]
    if category:
        match = re.search(r"\b" + category.replace("_", r"[ -]") + r"\b", text, re.I)
        method = "explicit_category"
        if not match:
            # Small illustrative catalog, never an operational aircraft specification.
            match = next(
                (
                    literal(model)
                    for model, group in AIRCRAFT
                    if group == category and literal(model)
                ),
                None,
            )
            method = "illustrative_aircraft_catalog"
        add("aircraft_category", category, match, method)
    returning = data["return_date"]
    add(
        "return_date",
        returning,
        next((m for m in dates if str(parse_date(m[0])) == returning), None),
        "date_normalization",
    )
    aliases = {
        "wifi": r"\bwi[ -]?fi\b|\binternet\b",
        "catering": r"\bcatering\b|\bmeals?\b",
        "pets": r"\bpets?\b|\bdog\b|\bcat\b",
        "wheelchair": r"\bwheelchair\b",
        "extra_luggage": r"\bextra (?:luggage|baggage)\b",
    }
    for requirement in data["special_requirements"]:
        pattern = aliases.get(requirement, re.escape(requirement))
        match = re.search(pattern, text, re.I)
        add("special_requirements", requirement, match, "mention_only_negation_not_verified")
    return evidence
