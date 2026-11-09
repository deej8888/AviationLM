"""Application domain registration; the extraction contracts remain industry-neutral."""

from aerolm.core import DomainRegistry, DomainSpec
from aerolm.domains.charter import CharterRequest, review_warnings
from aerolm.domains.grounding import source_evidence

registry = DomainRegistry()
registry.register(
    DomainSpec(
        name="charter",
        description="Charter flight requests",
        schema=CharterRequest,
        instructions=(
            "Preserve explicitly stated IATA/ICAO codes; do not choose airports for city names. "
            "Use ISO dates only when day, month and year are explicit; leave relative dates null. "
            "Use 24-hour time; Z/Zulu is UTC, explicitly local is local, otherwise null. "
            "A round trip uses an outbound leg and return_date. Multi-leg uses ordered legs. "
            "Normalize requirements to: catering, wifi, pets, wheelchair, extra_luggage. "
            "Include any other explicitly requested requirements verbatim. "
            "Keep budget currency as written. Do not infer trip_type unless stated."
        ),
        review=review_warnings,
        evidence=source_evidence,
    )
)
