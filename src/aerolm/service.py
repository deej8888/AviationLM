import json
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, Field, JsonValue, ValidationError

from aerolm.core import Backend, DomainRegistry
from aerolm.domains.registry import registry


class ExtractionError(Exception):
    """Output failed JSON/schema or configured evidence acceptance checks."""


class SourceEvidence(BaseModel):
    path: str
    value: JsonValue
    status: Literal["matched", "unverified"]
    quote: str | None = None
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    method: str


class ExtractionResult(BaseModel):
    schema_version: str = "1.0"
    domain: str
    backend: str
    model_id: str | None = None
    adapter_loaded: bool = False
    data: dict
    warnings: list[str]
    latency_ms: float = Field(ge=0)
    requires_review: bool = True
    evidence: list[SourceEvidence] = Field(default_factory=list)


def strict_json(raw: str) -> dict:
    """Reject markdown, duplicate keys, NaN, extra text, and non-object JSON."""

    def pairs(items: list[tuple]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError(f"Invalid JSON constant: {value}")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


class ExtractionService:
    def __init__(
        self,
        backend: Backend,
        domains: DomainRegistry = registry,
        evidence_policy: Literal["warn", "reject"] = "warn",
    ):
        self.backend, self.domains = backend, domains
        if evidence_policy not in {"warn", "reject"}:
            raise ValueError("Evidence policy must be warn or reject")
        self.evidence_policy = evidence_policy

    def extract(self, text: str, domain_name: str = "charter") -> ExtractionResult:
        spec = self.domains.get(domain_name)
        started = perf_counter()
        raw = self.backend.generate(text, spec)
        try:
            data = strict_json(raw)
            # Validate from JSON to accept ISO dates while refusing coercions such as "6" pax.
            parsed = spec.schema.model_validate_json(json.dumps(data), strict=True)
        except (ValueError, ValidationError) as error:
            raise ExtractionError("Model output failed JSON/schema validation") from error
        warnings = spec.review(parsed, text)
        evidence = spec.evidence(parsed, text) if spec.evidence else []
        unverified = sorted({item["path"] for item in evidence if item["status"] == "unverified"})
        if unverified:
            if self.evidence_policy == "reject":
                raise ExtractionError(
                    "Model output contains facts without recognized source evidence"
                )
            warnings.append("Source evidence not verified for: " + ", ".join(unverified) + ".")
        if self.backend.name == "rules":
            warnings.insert(
                0, "Rules baseline: limited pattern matching; no language model is loaded."
            )
        return ExtractionResult(
            domain=domain_name,
            backend=self.backend.name,
            model_id=getattr(self.backend, "model_id", None),
            adapter_loaded=bool(getattr(self.backend, "adapter_path", None)),
            data=parsed.model_dump(mode="json"),
            warnings=warnings,
            evidence=evidence,
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )
