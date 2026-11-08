"""Labels are constructed from sampled facts, never from the extraction baseline."""

import hashlib
import json
import random
from datetime import date, timedelta
from pathlib import Path

from aerolm.domains.charter import CharterRequest, FlightLeg

GENERATOR_VERSION = "1.0"
AIRPORTS = ["TEB", "MIA", "VNY", "LAS", "KDAL", "KASE", "LTN", "NCE", "GVA", "EGGW", "LFPB", "EDDM"]
AIRCRAFT = [
    ("Citation CJ3", "light_jet"),
    ("Phenom 300", "light_jet"),
    ("Citation XLS", "midsize_jet"),
    ("Challenger 350", "super_midsize_jet"),
    ("Gulfstream G650", "heavy_jet"),
    ("King Air 350", "turboprop"),
    ("Global 6000", "heavy_jet"),
    ("Pilatus PC-12", "turboprop"),
]
SERVICES = {
    "catering": "catering required",
    "wifi": "WiFi required",
    "pets": "one dog travelling",
    "wheelchair": "wheelchair assistance required",
    "extra_luggage": "extra luggage required",
}
# Whole phrasing families are held out. Similar facts can occur across splits by design.
TEMPLATES = {
    "train": [
        (
            "email",
            "Subject: Charter availability\nHi ops, please quote {trip} {origin} to {dest} on {day} at {time} {zone} for {pax} pax. {aircraft} preferred. {returning} {services} {budget} Reply: {contact}",
        ),
        (
            "broker",
            "Dear charter desk,\nOur client requests {pax} passengers on {origin} -> {dest}, {day}, {time} {zone}. {trip}; aircraft preference: {aircraft}. {services} {returning} {budget}\nRegards, {contact}",
        ),
        (
            "dispatch",
            "CHARTER RFQ / {trip}\nSector: {origin}-{dest}\nETD: {day} {time} {zone}\nLoad: {pax} pax\nEquipment: {aircraft}\n{returning}\n{services}\n{budget}\nContact {contact}",
        ),
        (
            "brief",
            "Can you source {aircraft} for {pax} people? {origin} to {dest} on {day}, depart {time} {zone}. {trip}. {returning} {services} {budget} Email {contact}.",
        ),
        (
            "availability",
            "Availability check: {origin}/{dest} {day} at {time} {zone}, {pax} guests, {trip}, {aircraft}. {services} {returning} {budget} {contact}",
        ),
    ],
    "validation": [
        (
            "assistant",
            "Good morning, I'm arranging a {trip} for {pax} passengers. Route {origin} to {dest}. Departure {day} {time} {zone}. We'd like {aircraft}. {returning} {services} {budget} Kindly respond to {contact}.",
        ),
        (
            "ops_note",
            "Dispatch note: {pax} pax, {aircraft}, {trip}. Routing {origin} -> {dest}; wheels up {day} {time} {zone}. {services} {returning} {budget} Follow up with {contact}.",
        ),
    ],
    "test": [
        (
            "concierge",
            "Hello team, could you help with a {trip} charter? We have {pax} guests flying {origin} to {dest} on {day} at {time} {zone}. Preferred equipment is {aircraft}. {services} {budget} {returning} You can reach us at {contact}.",
        ),
        (
            "rfq_card",
            "RFQ // {trip}\nRequested aircraft {aircraft}\nRouting {origin} -> {dest}\nDate {day}; ETD {time} {zone}\nParty {pax} passengers\n{services}\n{returning}\n{budget}\nDesk {contact}",
        ),
        (
            "travel_desk",
            "Travel desk to charter ops: please price {origin}-{dest}, {day}, {time} {zone}. {pax} pax and a preference for {aircraft}. This is {trip}. {returning} {services} {budget} Thanks, {contact}",
        ),
    ],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_split(split: str, count: int, seed: int) -> list[dict]:
    if split not in TEMPLATES or count < 1:
        raise ValueError("Expected a known split and positive count")
    rng = random.Random(f"aerolm:{GENERATOR_VERSION}:{seed}:{split}")
    rows, seen = [], set()
    while len(rows) < count:
        index = len(rows)
        family, template = rng.choice(TEMPLATES[split])
        origin, dest = rng.sample(AIRPORTS, 2)
        day = date(2027, 1, 1) + timedelta(days=rng.randrange(600))
        hour, minute = rng.randrange(6, 22), rng.choice([0, 15, 30, 45])
        clock = f"{hour:02d}:{minute:02d}"
        zone = rng.choice(["UTC", "local"])
        pax = rng.randint(1, 9)
        aircraft, category = rng.choice(AIRCRAFT)
        trip = rng.choice(["one-way", "round trip"])
        returning = day + timedelta(days=rng.randint(1, 8)) if trip == "round trip" else None
        requirements = sorted(rng.sample(list(SERVICES), rng.randrange(4)))
        budget = rng.choice([None, "USD 25,000", "EUR 18,000", "GBP 12,500"])
        contact = f"desk{rng.randrange(100)}@charter.example"
        date_text = day.strftime(rng.choice(["%Y-%m-%d", "%d %B %Y", "%B %d, %Y"]))
        expected = CharterRequest(
            trip_type="round_trip" if returning else "one_way",
            legs=[
                FlightLeg(
                    origin=origin,
                    destination=dest,
                    departure_date=day,
                    departure_time=clock,
                    time_zone=zone,
                )
            ],
            passengers=pax,
            aircraft_category=category,
            aircraft_preference=aircraft,
            return_date=returning,
            budget=budget,
            special_requirements=requirements,
            contact_email=contact,
        )
        text = template.format(
            origin=origin,
            dest=dest,
            day=date_text,
            time=clock,
            zone=zone,
            pax=pax,
            aircraft=aircraft,
            trip=trip,
            returning=f"Return {returning.isoformat()}." if returning else "",
            services="; ".join(SERVICES[key] for key in requirements)
            + ("." if requirements else ""),
            budget=f"Budget {budget}." if budget else "",
            contact=contact,
        )
        # Missing and relative facts teach abstention, including cities with no selected airport.
        if index % 10 == 0:
            text = text.replace(date_text, "next Friday")
            expected.legs[0].departure_date = None
        if index % 13 == 0:
            text = text.replace(str(pax) + " pax", "passenger count TBD")
            text = text.replace(str(pax) + " passengers", "passenger count TBD")
            text = text.replace(str(pax) + " people", "passenger count TBD")
            text = text.replace(str(pax) + " guests", "passenger count TBD")
            expected.passengers = None
        if index % 17 == 0:
            text = text.replace(origin, "London")
            expected.legs[0].origin = None
        digest = hashlib.sha256(text.encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        rows.append(
            {
                "id": f"{split}-{index:05d}",
                "split": split,
                "template_family": family,
                "text": text,
                "expected": expected.model_dump(mode="json"),
                "provenance": "synthetic",
                "license": "CC0-1.0",
            }
        )
    return rows


def generate_dataset(
    output: Path, seed: int = 42, train: int = 1000, validation: int = 120, test: int = 120
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "license": "CC0-1.0",
        "provenance": "synthetic",
        "splits": {},
    }
    seen = set()
    for split, count in (("train", train), ("validation", validation), ("test", test)):
        rows = generate_split(split, count, seed)
        for row in rows:
            if row["text"] in seen:
                raise ValueError("Duplicate text across splits")
            seen.add(row["text"])
        path = output / f"{split}.jsonl"
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
            newline="\n",
        )
        manifest["splits"][split] = {
            "count": count,
            "sha256": sha256(path),
            "template_families": [key for key, _ in TEMPLATES[split]],
        }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
