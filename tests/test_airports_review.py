from fastapi.testclient import TestClient

from aerolm.api import create_app
from aerolm.backends.rules import RulesBackend
from aerolm.domains.airports import airport_checks, load_reference
from aerolm.domains.charter import CharterRequest, FlightLeg
from aerolm.service import ExtractionService
from aerolm.settings import Settings


def test_airport_reference_matches_iata_and_icao_and_flags_unknowns():
    meta, index = load_reference()
    assert meta["record_count"] == 19721
    assert index["TEB"][0]["icao_code"] == "KTEB"
    assert index["KTEB"][0]["iata_code"] == "TEB"
    request = CharterRequest(legs=[FlightLeg(origin="TEB", destination="KBOB")])
    checks = airport_checks(request, "TEB to KBOB")
    assert (
        checks[0]["status"] == "matched" and checks[0]["matches"][0]["name"] == "Teterboro Airport"
    )
    assert checks[1]["status"] == "not_found" and checks[1]["match_count"] == 0
    assert request.legs[0].destination == "KBOB"  # No silent correction.


def test_reference_failure_is_visible_and_does_not_break_extraction(monkeypatch):
    import aerolm.domains.airports as airports

    def unavailable():
        raise OSError("snapshot missing")

    monkeypatch.setattr(airports, "load_reference", unavailable)
    result = ExtractionService(RulesBackend()).extract("One-way TEB to MIA, 6 passengers.")
    assert len(result.checks) == 2
    assert all(c.status == "unavailable" for c in result.checks)
    assert any("reference unavailable" in w for w in result.warnings)


def test_review_revalidates_corrections_and_recomputes_source_and_airport_checks():
    app = create_app(Settings(backend="rules", api_key=""))
    with TestClient(app) as client:
        text = "One-way TEB to MIA, 6 passengers."
        initial = client.post("/v1/extract", json={"text": text}).json()
        assert all(c["status"] == "matched" for c in initial["checks"])
        edited = initial["data"]
        edited["legs"][0]["destination"] = "KBOB"
        edited["passengers"] = 8
        response = client.post("/v1/review", json={"text": text, "data": edited})
        assert response.status_code == 200
        body = response.json()
        assert body["requires_review"] and body["data"]["passengers"] == 8
        assert (
            next(c for c in body["checks"] if c["path"] == "legs[0].destination")["status"]
            == "not_found"
        )
        assert (
            next(e for e in body["evidence"] if e["path"] == "passengers")["status"] == "unverified"
        )
        assert any("KBOB" in warning for warning in body["warnings"])
        edited["passengers"] = "8"
        assert client.post("/v1/review", json={"text": text, "data": edited}).status_code == 422
