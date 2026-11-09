from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient

from aerolm.api import create_app
from aerolm.backends.rules import RulesBackend
from aerolm.service import ExtractionService
from aerolm.settings import Settings


def test_cpu_api_contract_and_discovery():
    with TestClient(create_app(Settings(backend="rules", api_key=""))) as client:
        assert client.get("/healthz").json()["backend"] == "rules"
        assert client.get("/v1/domains").json()[0]["id"] == "charter"
        assert client.get("/v1/schema/charter").json()["title"] == "CharterRequest"
        assert client.get("/v1/schema/maintenance").status_code == 404
        example = client.get("/v1/examples").json()[0]
        result = client.post("/v1/extract", json={"text": example["text"]})
        assert result.status_code == 200
        assert result.json()["data"]["passengers"] == 6
        assert result.json()["requires_review"]
        assert "reports" in client.get("/v1/benchmarks").json()


def test_validation_and_optional_auth():
    with TestClient(create_app(Settings(api_key="test-secret"))) as client:
        assert client.post("/v1/extract", json={"text": "test"}).status_code == 401
        headers = {"Authorization": "Bearer test-secret"}
        for payload in (
            {"text": " "},
            {"text": "a" * 12001},
            {"text": "x", "domain": "crew"},
            {"text": "x", "extra": 1},
        ):
            assert client.post("/v1/extract", json=payload, headers=headers).status_code == 422
        assert client.post("/v1/extract", json={"text": "test"}, headers=headers).status_code == 200


def test_invalid_model_output_is_not_returned_as_success():
    class BadBackend:
        name = "test"

        def generate(self, text, domain):
            return "not JSON"

    with TestClient(create_app(Settings(api_key=""), ExtractionService(BadBackend()))) as client:
        response = client.post("/v1/extract", json={"text": "test"})
        assert response.status_code == 502
        assert "not JSON" not in response.text


def test_model_calls_do_not_queue_unboundedly():
    started, release = Event(), Event()

    class BlockingBackend(RulesBackend):
        def generate(self, text, domain):
            started.set()
            release.wait(timeout=5)
            return super().generate(text, domain)

    with TestClient(
        create_app(Settings(api_key=""), ExtractionService(BlockingBackend()))
    ) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(client.post, "/v1/extract", json={"text": "TEB to MIA"})
            assert started.wait(timeout=3)
            try:
                response = client.post("/v1/extract", json={"text": "TEB to MIA"})
                assert response.status_code == 503 and response.headers["retry-after"] == "2"
            finally:
                release.set()
            assert pending.result().status_code == 200


def test_api_rejects_unverified_facts_when_service_uses_strict_evidence_policy():
    class InventedContact:
        name = "test"

        def generate(self, text, domain):
            return '{"contact_email":"invented@sample.example"}'

    service = ExtractionService(InventedContact(), evidence_policy="reject")
    with TestClient(create_app(Settings(api_key=""), service)) as client:
        response = client.post("/v1/extract", json={"text": "Please advise availability."})
        assert response.status_code == 502
        assert "invented@sample.example" not in response.text
