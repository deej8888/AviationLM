"""Conservative, intentionally limited baseline. No airport directory or external service."""

import re
from datetime import date, datetime

from aerolm.core import DomainSpec
from aerolm.domains.charter import CharterRequest, FlightLeg

AIRPORT = r"(?:[A-Z]{4}|[A-Z]{3})"
ROUTE = re.compile(rf"\b({AIRPORT})\s*(?:->|→|–|-|/|\bto\b)\s*({AIRPORT})\b")
MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE = re.compile(
    rf"\b(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}\s+{MONTH}\s+\d{{4}}|{MONTH}\s+\d{{1,2}},?\s+\d{{4}})\b",
    re.I,
)
AIRCRAFT = [
    ("Citation CJ3", "light_jet"),
    ("Phenom 300", "light_jet"),
    ("Citation XLS", "midsize_jet"),
    ("Hawker 800XP", "midsize_jet"),
    ("Challenger 350", "super_midsize_jet"),
    ("Citation Latitude", "super_midsize_jet"),
    ("Gulfstream G650", "heavy_jet"),
    ("Global 6000", "heavy_jet"),
    ("King Air 350", "turboprop"),
    ("Pilatus PC-12", "turboprop"),
]
REQUIREMENTS = {
    "catering": r"\bcatering\b|\bhot meals?\b",
    "wifi": r"\bwi[ -]?fi\b|\binternet\b",
    "pets": r"\bpets?\b|\bdog\b|\bcat\b",
    "wheelchair": r"\bwheelchair\b",
    "extra_luggage": r"\bextra (?:luggage|baggage)\b|\bgolf (?:clubs|bags)\b",
}


def parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(value.replace(",", ""), fmt).date()
        except ValueError:
            continue
    return None


def parse_time(text: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"\b([01]?\d|2[0-3]):([0-5]\d)\s*(am|pm)?\s*(Z|Zulu|UTC|local)?\b", text, re.I
    )
    if not match:
        match = re.search(r"\b([01]\d|2[0-3])([0-5]\d)\s*(Z|Zulu|UTC)\b", text, re.I)
        if match:
            return f"{match[1]}:{match[2]}", "UTC"
        return None, None
    hour = int(match[1])
    if match[3]:
        if not 1 <= hour <= 12:
            return None, None
        hour = hour % 12 + (12 if match[3].lower() == "pm" else 0)
    zone = match[4]
    return f"{hour:02d}:{match[2]}", (
        "local" if zone.lower() == "local" else "UTC"
    ) if zone else None


class RulesBackend:
    name = "rules"

    def generate(self, text: str, domain: DomainSpec) -> str:
        if domain.name != "charter":
            raise ValueError("Rules backend supports only charter; register a domain backend.")
        body = re.sub(r"^Subject:.*(?:\n|$)", "", text, flags=re.I | re.M)
        if ROUTE.search(body):
            text = body  # A repeated subject-line route is not a second flight leg.
        routes = list(ROUTE.finditer(text))
        legs = []
        for index, route in enumerate(routes):
            end = routes[index + 1].start() if index + 1 < len(routes) else len(text)
            segment = text[route.end() : end]
            # Return dates belong to the itinerary, not a new outbound leg.
            segment = re.split(r"\b(?:return(?:ing)?|back)\b", segment, flags=re.I)[0]
            found_date = DATE.search(segment)
            departure_time, time_zone = parse_time(segment)
            legs.append(
                FlightLeg(
                    origin=route[1],
                    destination=route[2],
                    departure_date=parse_date(found_date[0]) if found_date else None,
                    departure_time=departure_time,
                    time_zone=time_zone,
                )
            )
        # A known code with an ambiguous city still deserves a partial leg.
        if not legs:
            origin = re.search(rf"\bfrom\s+({AIRPORT})\b", text)
            destination = re.search(rf"\bto\s+({AIRPORT})\b", text)
            found_date = DATE.search(text)
            if origin or destination or found_date:
                departure_time, time_zone = parse_time(text)
                legs.append(
                    FlightLeg(
                        origin=origin[1] if origin else None,
                        destination=destination[1] if destination else None,
                        departure_date=parse_date(found_date[0]) if found_date else None,
                        departure_time=departure_time,
                        time_zone=time_zone,
                    )
                )
        pax = re.search(r"\b(\d{1,4})\s*(?:pax|passengers?|people|guests?)\b", text, re.I)
        passengers = int(pax[1]) if pax and 1 <= int(pax[1]) <= 1000 else None
        aircraft, category = None, None
        for model, group in AIRCRAFT:
            if model.lower() in text.lower():
                aircraft, category = model, group
                break
        if not category:
            for group in (
                "super_midsize_jet",
                "midsize_jet",
                "light_jet",
                "heavy_jet",
                "turboprop",
                "helicopter",
            ):
                if re.search(r"\b" + group.replace("_", r"[ -]") + r"\b", text, re.I):
                    category = group
                    break
        trip_type = None
        if re.search(r"\bround[ -]?trip\b|\breturn(?:ing)?\b", text, re.I):
            trip_type = "round_trip"
        elif len(legs) > 1:
            trip_type = "multi_leg"
        elif re.search(r"\bone[ -]?way\b", text, re.I):
            trip_type = "one_way"
        return_match = re.search(r"\b(?:return(?:ing)?|back)\b", text, re.I)
        return_match_date = DATE.search(text[return_match.end() :]) if return_match else None
        return_date = parse_date(return_match_date[0]) if return_match_date else None
        if return_date and legs and legs[0].departure_date and return_date < legs[0].departure_date:
            return_date = None
        requirements = []
        for key, pattern in REQUIREMENTS.items():
            # Negated mentions should not be converted to requested services.
            cleaned = re.sub(
                rf"\b(?:no|without|do not need|don't need|not required:?)\s+(?:{pattern})",
                "",
                text,
                flags=re.I,
            )
            if re.search(pattern, cleaned, re.I):
                requirements.append(key)
        budget = re.search(
            r"\bbudget\s*(?:of|is|:|under|up to)?\s*((?:USD|EUR|GBP|\$|€|£)\s*[\d,]+(?:\.\d{2})?)",
            text,
            re.I,
        )
        email = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I)
        return CharterRequest(
            trip_type=trip_type,
            legs=legs,
            passengers=passengers,
            aircraft_category=category,
            aircraft_preference=aircraft,
            return_date=return_date,
            budget=budget[1].strip() if budget else None,
            special_requirements=sorted(requirements),
            contact_email=email[0] if email else None,
        ).model_dump_json()
