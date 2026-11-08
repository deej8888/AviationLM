"""Local inference API. No email body storage, remote calls, or content logging."""

import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from threading import BoundedSemaphore
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from aerolm import __version__
from aerolm.backends.rules import RulesBackend
from aerolm.domains.registry import registry
from aerolm.examples import EXAMPLES
from aerolm.service import ExtractionError, ExtractionResult, ExtractionService
from aerolm.settings import Settings

REPORT_DIR = Path("benchmarks/results")


class ExtractionInput(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    domain: str = Field(default="charter", max_length=64)
    model_config = {"extra": "forbid"}


def create_app(
    settings: Settings | None = None, service: ExtractionService | None = None
) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if service:
            app.state.service = service
        elif config.backend == "hf":
            from aerolm.backends.huggingface import HuggingFaceBackend

            app.state.service = ExtractionService(HuggingFaceBackend(config))
        else:
            app.state.service = ExtractionService(RulesBackend())
        app.state.gate = BoundedSemaphore(1)
        yield

    app = FastAPI(title="AeroLM", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    bearer = HTTPBearer(auto_error=False)

    def authorize(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if config.api_key and (
            credentials is None
            or not secrets.compare_digest(credentials.credentials, config.api_key)
        ):
            raise HTTPException(
                401, "Valid bearer token required", headers={"WWW-Authenticate": "Bearer"}
            )

    @app.get("/healthz")
    def health(request: Request):
        backend = request.app.state.service.backend
        return {
            "status": "ok",
            "version": __version__,
            "backend": backend.name,
            "model_id": getattr(backend, "model_id", None),
            "adapter_loaded": bool(getattr(backend, "adapter_path", None)),
        }

    @app.get("/v1/domains")
    def domains():
        return [{"id": spec.name, "description": spec.description} for spec in registry.list()]

    @app.get("/v1/schema/{domain}")
    def schema(domain: str):
        try:
            return registry.get(domain).schema.model_json_schema()
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/v1/examples")
    def examples():
        return EXAMPLES

    @app.get("/v1/benchmarks")
    def benchmarks():
        reports = []
        for path in sorted(REPORT_DIR.glob("*.json")):
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        return {
            "reports": reports,
            "model_status": "No trained adapter is bundled; see reports for measured runs.",
        }

    @app.post("/v1/extract", response_model=ExtractionResult, dependencies=[Depends(authorize)])
    def extract(body: ExtractionInput, request: Request):
        if not body.text.strip():
            raise HTTPException(422, "Request text cannot be blank")
        if body.domain not in [spec.name for spec in registry.list()]:
            raise HTTPException(422, "Unsupported domain")
        if not request.app.state.gate.acquire(blocking=False):
            raise HTTPException(503, "Inference busy; retry shortly", headers={"Retry-After": "2"})
        try:
            return request.app.state.service.extract(body.text, body.domain)
        except ExtractionError as error:
            raise HTTPException(
                502, "Model returned invalid structured output; no extraction accepted"
            ) from error
        except ValueError as error:
            raise HTTPException(422, "Request exceeds model limits or is unsupported") from error
        finally:
            request.app.state.gate.release()

    return app


app = create_app()
