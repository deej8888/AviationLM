"""Versioned synthetic facts -> text generator; v1 fixtures remain immutable.

Evidence is a construction ledger, not an independent human annotation. Omissions are
sampled before rendering so labels never retain facts removed by string replacement.
"""

import hashlib
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from aerolm.data.generate import AIRCRAFT, AIRPORTS, sha256
from aerolm.domains.charter import CharterRequest, FlightLeg
from aerolm.evaluation import facts

VERSION = "2.0"
SCENARIOS = (
    "complete",
    "sparse",
    "sparse",
    "ambiguous",
    "negation",
    "correction",
    "multi_leg",
    "unknown_aircraft",
    "empty",
    "complete",
)
FAMILIES = {
    "train": ("ops_email", "broker_note", "quick_message", "dispatch_list"),
    "validation": ("intake_note", "assistant_memo"),
    "test": ("travel_form", "concierge_handoff", "customer_rfq"),
}
INTRO = {
    "ops_email": "Subject: Charter enquiry\nHello operations, please review:",
    "broker_note": "Broker to charter desk. Client's requirements follow:",
    "quick_message": "Hi, could you check charter availability?",
    "dispatch_list": "CHARTER / REQUEST DETAILS",
    "intake_note": "New charter intake for review:",
    "assistant_memo": "Please help arrange the following private flight:",
    "travel_form": "Travel request received by the desk:",
    "concierge_handoff": "Concierge handoff: please source options using these details.",
    "customer_rfq": "Request for a charter quotation:",
}
WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}


class Ledger:
    def __init__(self):
        self.evidence: list[dict] = []

    def record(self, quote: str, values: dict) -> str:
        for path, value in facts(values):
            if any(e["path"] == path and e["value"] == json.loads(value) for e in self.evidence):
                raise ValueError(f"Duplicate gold evidence: {path}")
            self.evidence.append({"path": path, "quote": quote, "value": json.loads(value)})
        return quote

    def leg(self, index: int, quote: str, values: dict) -> str:
        # Match the evaluator's canonical indexed field paths, without padding legs.
        for key, value in values.items():
            if value is not None:
                self.evidence.append(
                    {"path": f"legs[{index}].{key}", "quote": quote, "value": value}
                )
        return quote


def coverage(rows: list[dict]) -> dict:
    scalar = (
        "trip_type",
        "passengers",
        "aircraft_category",
        "aircraft_preference",
        "return_date",
        "budget",
        "contact_email",
    )
    leg_fields = tuple(FlightLeg.model_fields)
    legs = [leg for row in rows for leg in row["expected"]["legs"]]
    return {
        "scenarios": dict(sorted(Counter(r["scenario"] for r in rows).items())),
        "missing_fields": {k: sum(r["expected"][k] is None for r in rows) for k in scalar},
        "missing_leg_fields": {k: sum(leg[k] is None for leg in legs) for k in leg_fields},
        "total_legs": len(legs),
        "multi_leg_requests": sum(len(r["expected"]["legs"]) > 1 for r in rows),
        "empty_requests": sum(not facts(r["expected"]) for r in rows),
    }


def validate_ledger(row: dict) -> None:
    expected = facts(row["expected"])
    recorded = {(v["path"], json.dumps(v["value"], sort_keys=True)) for v in row["evidence"]}
    if recorded != expected or any(v["quote"] not in row["text"] for v in row["evidence"]):
        raise ValueError(f"Gold facts/evidence mismatch: {row['id']}")
    CharterRequest.model_validate_json(json.dumps(row["expected"]), strict=True)


def generate_robust_split(split: str, count: int, seed: int) -> list[dict]:
    if split not in FAMILIES or count < 1:
        raise ValueError("Expected a known split and positive count")
    rng = random.Random(f"aerolm:{VERSION}:{seed}:{split}")
    rows = []
    for index in range(count):
        scenario = SCENARIOS[index % len(SCENARIOS)]
        family = rng.choice(FAMILIES[split])
        ledger = Ledger()
        value = CharterRequest()
        blocks = []
        sparse = scenario in {"sparse", "ambiguous", "negation", "correction"}

        def present(probability: float, sparse: bool = sparse) -> bool:
            return not sparse or rng.random() < probability

        if scenario == "empty":
            # Independent fictional references keep identical empty requests out of splits.
            blocks.append(
                f"Enquiry reference {rng.randrange(10**8, 10**9)}. "
                "Please advise charter availability; itinerary details will follow."
            )
        else:
            nlegs = rng.choice([2, 3]) if scenario == "multi_leg" else 1
            airports = AIRPORTS + (["KJFK", "KLAX", "KSFO", "KBOS"] if split == "test" else [])
            route = rng.sample(airports, nlegs + 1)
            base_day = date(2027, 1, 1) + timedelta(days=rng.randrange(730))
            for leg_index in range(nlegs):
                day = base_day + timedelta(days=leg_index * rng.randint(1, 3))
                clock = f"{rng.randrange(6, 22):02d}:{rng.choice([0, 15, 30, 45]):02d}"
                zone = rng.choice(["UTC", "local"]) if present(0.45) else None
                leg = FlightLeg(
                    origin=route[leg_index] if present(0.8) else None,
                    destination=route[leg_index + 1] if present(0.8) else None,
                    departure_date=day if present(0.55) else None,
                    departure_time=clock if present(0.45) else None,
                    time_zone=zone,
                )
                if leg.departure_time is None:
                    leg.time_zone = None
                if scenario == "ambiguous":
                    leg.departure_date = None
                    leg.departure_time = None
                    leg.time_zone = None
                parts = []
                raw_origin = leg.origin or "London (airport undecided)"
                raw_dest = leg.destination or "Paris (airport undecided)"
                if rng.random() < 0.3:
                    raw_origin, raw_dest = raw_origin.lower(), raw_dest.lower()
                routing = rng.choice(
                    [
                        f"From {raw_origin} to {raw_dest}",
                        f"Origin: {raw_origin}; destination: {raw_dest}",
                        f"Routing {raw_origin} -> {raw_dest}",
                    ]
                )
                parts.append(
                    ledger.leg(
                        leg_index, routing, {"origin": leg.origin, "destination": leg.destination}
                    )
                )
                if leg.departure_date:
                    rendered = day.strftime(rng.choice(["%Y-%m-%d", "%d %B %Y", "%B %d, %Y"]))
                    quote = f"Departure date {rendered}"
                    parts.append(ledger.leg(leg_index, quote, {"departure_date": day.isoformat()}))
                elif scenario == "ambiguous":
                    parts.append(
                        rng.choice(
                            [
                                "Departure next Friday (date unconfirmed)",
                                "Date 03/04/27; format unconfirmed",
                                "Date TBD",
                            ]
                        )
                    )
                if leg.departure_time:
                    hour, minute = map(int, clock.split(":"))
                    if rng.random() < 0.35:
                        rendered = f"{hour % 12 or 12}:{minute:02d} {'pm' if hour >= 12 else 'am'}"
                    elif leg.time_zone == "UTC" and rng.random() < 0.5:
                        rendered = clock.replace(":", "") + "Z"
                    else:
                        rendered = clock
                    suffix = f" {leg.time_zone}" if leg.time_zone else " (timezone not specified)"
                    quote = "ETD " + rendered + suffix
                    parts.append(
                        ledger.leg(
                            leg_index, quote, {"departure_time": clock, "time_zone": leg.time_zone}
                        )
                    )
                prefix = f"Leg {leg_index + 1}: " if nlegs > 1 else ""
                blocks.append(prefix + "; ".join(parts) + ".")
                value.legs.append(leg)
            if present(0.35):
                value.trip_type = (
                    "multi_leg" if nlegs > 1 else rng.choice(["one_way", "round_trip"])
                )
                quote = {
                    "multi_leg": "This is a multi-leg itinerary.",
                    "one_way": "One-way request.",
                    "round_trip": "Round trip requested.",
                }[value.trip_type]
                blocks.append(ledger.record(quote, {"trip_type": value.trip_type}))
                if value.trip_type == "round_trip" and rng.random() < 0.7:
                    value.return_date = base_day + timedelta(days=10)
                    quote = f"Return {value.return_date.isoformat()}."
                    blocks.append(
                        ledger.record(quote, {"return_date": value.return_date.isoformat()})
                    )
            if scenario == "correction" or present(0.65):
                value.passengers = rng.randint(1, 12)
                token = WORDS[value.passengers] if rng.random() < 0.4 else str(value.passengers)
                quote = f"{token} passengers travelling."
                if scenario == "correction":
                    old = value.passengers % 12 + 1
                    quote = (
                        f"Previous message: {old} pax. "
                        f"Correction: passenger count is now {token} passengers."
                    )
                blocks.append(ledger.record(quote, {"passengers": value.passengers}))
            else:
                blocks.append("Passenger count TBD.")
            if present(0.3):
                if scenario == "unknown_aircraft":
                    value.aircraft_preference = f"ExampleAir {rng.randrange(100, 999)}"
                    quote = (
                        f"Preferred aircraft: {value.aircraft_preference}; category unconfirmed."
                    )
                else:
                    value.aircraft_preference, value.aircraft_category = rng.choice(AIRCRAFT)
                    quote = f"Preferred aircraft: {value.aircraft_preference}."
                blocks.append(
                    ledger.record(
                        quote,
                        {
                            "aircraft_preference": value.aircraft_preference,
                            "aircraft_category": value.aircraft_category,
                        },
                    )
                )
            elif rng.random() < 0.25:
                value.aircraft_category = rng.choice(["light_jet", "heavy_jet", "helicopter"])
                quote = f"Aircraft category: {value.aircraft_category.replace('_', ' ')}."
                blocks.append(ledger.record(quote, {"aircraft_category": value.aircraft_category}))
            if present(0.2):
                value.contact_email = f"agent{rng.randrange(100000)}@synthetic.example"
                quote = f"Reply to {value.contact_email}."
                blocks.append(ledger.record(quote, {"contact_email": value.contact_email}))
            if rng.random() < 0.35:
                currency, amount = rng.choice(
                    [("USD", "25,000"), ("EUR", "18,000"), ("GBP", "12,500")]
                )
                value.budget = rng.choice([f"{currency} {amount}", f"{amount} {currency}"])
                blocks.append(ledger.record(f"Budget {value.budget}.", {"budget": value.budget}))
            if scenario == "negation":
                value.special_requirements = ["wifi"]
                quote = rng.choice(
                    [
                        "No catering or pets. WiFi required.",
                        "Catering is not required; no pets. Please provide WiFi.",
                    ]
                )
                blocks.append(ledger.record(quote, {"special_requirements": ["wifi"]}))
            elif rng.random() < 0.4:
                options = [
                    ("wifi", "WiFi required."),
                    ("pets", "One dog will travel."),
                    ("wheelchair", "Wheelchair assistance required."),
                    ("catering", "Catering requested."),
                    ("kosher meals", "Please arrange kosher meals."),
                ]
                for name, _quote in rng.sample(options, rng.randint(1, 2)):
                    value.special_requirements.append(name)
                    # Separate requirement items share one fact path; retain a common quote below.
                quote = " ".join(q for name, q in options if name in value.special_requirements)
                blocks.append(
                    ledger.record(
                        quote, {"special_requirements": sorted(value.special_requirements)}
                    )
                )
                value.special_requirements.sort()
            # Preserve itinerary leg order; reorder the global request clauses only.
            common = blocks[nlegs:]
            rng.shuffle(common)
            blocks = blocks[:nlegs] + common
        separator = "\n- " if family in {"dispatch_list", "travel_form", "intake_note"} else "\n"
        text = INTRO[family] + separator + separator.join(blocks)
        row = {
            "id": f"v2-{split}-{index:05d}",
            "split": split,
            "template_family": family,
            "scenario": scenario,
            "text": text,
            "expected": value.model_dump(mode="json"),
            "evidence": ledger.evidence,
            "provenance": "synthetic",
            "license": "CC0-1.0",
        }
        validate_ledger(row)
        rows.append(row)
    return rows


def generate_robust_dataset(
    output: Path, seed: int = 84, train: int = 2000, validation: int = 200, test: int = 300
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise ValueError("Refusing to overwrite a versioned dataset; choose a new output directory")
    manifest = {
        "generator_version": VERSION,
        "profile": "robust-charter-v2",
        "seed": seed,
        "provenance": "synthetic",
        "license": "CC0-1.0",
        "annotation_review": (
            "Programmatic ledger and automated checks; no independent human review"
        ),
        "splits": {},
    }
    seen = set()
    for split, count in (("train", train), ("validation", validation), ("test", test)):
        rows = generate_robust_split(split, count, seed)
        for row in rows:
            digest = hashlib.sha256(row["text"].encode()).hexdigest()
            if digest in seen:
                raise ValueError("Duplicate text across robust dataset splits")
            seen.add(digest)
        path = output / f"{split}.jsonl"
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
            newline="\n",
        )
        manifest["splits"][split] = {
            "count": count,
            "sha256": sha256(path),
            "template_families": list(FAMILIES[split]),
            "coverage": coverage(rows),
        }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
