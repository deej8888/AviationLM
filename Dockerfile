FROM python:3.12-slim AS api
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY benchmarks ./benchmarks
RUN uv sync --frozen --no-dev --no-editable && useradd --create-home --uid 10001 aerolm
USER aerolm
ENV PATH="/app/.venv/bin:$PATH" AEROLM_BACKEND=rules
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["uvicorn", "aerolm.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
