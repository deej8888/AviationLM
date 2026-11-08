import json

import pytest
from pydantic import BaseModel, ValidationError

from aerolm.backends.rules import RulesBackend
from aerolm.core import DomainRegistry, DomainSpec
from aerolm.domains.charter import CharterRequest
from aerolm.examples import EXAMPLES
from aerolm.service import ExtractionError, ExtractionService, strict_json


def test_complete_charter_and_review():
    result = ExtractionService(RulesBackend()).extract(EXAMPLES[0]["text"])
    assert result.backend == "rules" and result.model_id is None and not result.adapter_loaded
    assert result.data["legs"] == [
        {
            "origin": "TEB",
            "destination": "MIA",
            "departure_date": "2027-03-18",
            "departure_time": "09:30",
            "time_zone": "local",
        }
    ]
    assert result.data["passengers"] == 6
    assert result.data["return_date"] == "2027-03-21"
    assert result.data["budget"] == "USD 35,000"
    assert result.data["special_requirements"] == ["catering", "wifi"]
    assert result.requires_review and "Human review" in result.warnings[-1]


def test_city_and_relative_dates_are_not_invented():
    result = ExtractionService(RulesBackend()).extract(EXAMPLES[3]["text"])
    assert result.data["legs"] == []
    assert result.data["passengers"] is None
    assert result.data["special_requirements"] == []
    assert any("airport" in warning for warning in result.warnings)


def test_multi_leg_and_zulu_time():
    service = ExtractionService(RulesBackend())
    result = service.extract(EXAMPLES[2]["text"])
    assert result.data["trip_type"] == "multi_leg"
    assert len(result.data["legs"]) == 2
    assert result.data["legs"][1]["departure_date"] == "2027-05-12"
    assert service.extract(EXAMPLES[1]["text"]).data["legs"][0]["departure_time"] == "14:00"


@pytest.mark.parametrize(
    "raw", ["```json\n{}\n```", '{"a":1,"a":2}', "[]", '{"a":NaN}', "{} trailing"]
)
def test_strict_json_rejects_nonconformant_output(raw):
    with pytest.raises(ValueError):
        strict_json(raw)


@pytest.mark.parametrize(
    "raw",
    [
        '{"passengers":"6"}',
        '{"passengers":0}',
        '{"unknown":"value"}',
        '{"legs":[{"departure_date":"2027-02-31"}]}',
    ],
)
def test_service_rejects_bad_model_output(raw):
    class BadBackend:
        name = "test"

        def generate(self, text, domain):
            return raw

    with pytest.raises(ExtractionError):
        ExtractionService(BadBackend()).extract("Please quote")


def test_return_cannot_precede_departure():
    with pytest.raises(ValidationError):
        CharterRequest.model_validate_json(
            json.dumps(
                {
                    "return_date": "2027-01-01",
                    "legs": [{"departure_date": "2027-02-01"}],
                }
            )
        )


def test_extensible_to_unrelated_domain():
    class Ticket(BaseModel):
        priority: str

    domain = DomainSpec(
        "support", "Support triage", Ticket, "Extract priority", lambda value, text: []
    )
    domains = DomainRegistry()
    domains.register(domain)

    class SupportBackend:
        name = "test"

        def generate(self, text, domain):
            assert "priority" in domain.messages(text)[0]["content"]
            return '{"priority":"urgent"}'

    assert ExtractionService(SupportBackend(), domains).extract("urgent", "support").data == {
        "priority": "urgent"
    }
    with pytest.raises(ValueError, match="already registered"):
        domains.register(domain)
