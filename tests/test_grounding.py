import json

import pytest

from aerolm.domains.charter import CharterRequest, FlightLeg
from aerolm.domains.grounding import source_evidence
from aerolm.service import ExtractionError, ExtractionService


class FixedBackend:
    name = "test"

    def __init__(self, value):
        self.value = value

    def generate(self, text, domain):
        return json.dumps(self.value)


def test_invented_fields_are_flagged_without_rewriting_the_output():
    value = {
        "passengers": 6,
        "contact_email": "invented@sample.example",
        "legs": [{"origin": "TEB", "destination": "MIA", "departure_time": "06:00"}],
    }
    text = "TEB to MIA for six passengers."
    result = ExtractionService(FixedBackend(value)).extract(text)
    unverified = {e.path for e in result.evidence if e.status == "unverified"}
    assert unverified == {"contact_email", "legs[0].departure_time"}
    assert result.data["contact_email"] == value["contact_email"]
    assert any("Source evidence not verified" in w for w in result.warnings)
    for e in result.evidence:
        if e.status == "matched":
            assert text[e.start : e.end] == e.quote
    with pytest.raises(ExtractionError, match="source evidence"):
        ExtractionService(FixedBackend(value), evidence_policy="reject").extract(text)


def test_normalized_dates_times_and_word_counts_have_source_quotes():
    value = CharterRequest(
        passengers=6,
        legs=[
            FlightLeg(
                origin="TEB",
                destination="MIA",
                departure_date="2027-03-18",
                departure_time="14:30",
                time_zone="local",
            )
        ],
    )
    rows = source_evidence(value, "teb to mia on March 18, 2027 at 2:30 pm local. Six passengers.")
    assert all(e["status"] == "matched" for e in rows)


def test_mention_checks_explicitly_do_not_claim_to_verify_negation():
    rows = source_evidence(CharterRequest(special_requirements=["catering"]), "No catering.")
    assert rows[0]["method"] == "negated_mention_needs_review"
    assert rows[0]["status"] == "unverified"
    positive = source_evidence(CharterRequest(special_requirements=["wifi"]), "WiFi requested.")
    assert positive[0]["method"] == "mention_only_negation_not_verified"


def test_conflicting_counts_are_flagged_instead_of_treating_either_mention_as_proof():
    text = "Previous message: eight passengers. Correction: four passengers."
    for count in (4, 8):
        rows = source_evidence(CharterRequest(passengers=count), text)
        assert rows[0]["method"] == "conflicting_passenger_mentions"
        assert rows[0]["status"] == "unverified"


def test_literal_null_is_not_contact_evidence_even_when_it_occurs_in_the_text():
    rows = source_evidence(CharterRequest(contact_email="null"), "Contact: null.")
    assert rows[0]["status"] == "unverified"
