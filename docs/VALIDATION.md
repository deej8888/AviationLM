# Local validation record

Executed November 8, 2026 on Windows with Python 3.12.13, Node 24.18.0,
uv 0.11.32, and the committed dependency locks.

| Check | Observed result |
| --- | --- |
| `uv run --no-sync pytest` with ML dependencies installed | 30 passed |
| `uv run --no-sync python scripts/verify_benchmarks.py` | Both committed reports reproduced exactly for scores, fields, prompt and dataset hashes |
| `uv build` | Source distribution and wheel built successfully |
| `npm run build` in `web/` | Next.js production build and TypeScript checks passed |
| `npm run test:e2e` in `web/` | 8 passed, desktop and mobile Chromium, using the actual local API |
| `npm audit --omit=dev --audit-level=high` | 0 production advisories reported at execution time |
| Locked GPU dependency export | Export succeeded; container execution was not tested |
| Qwen3-0.6B tokenizer preflight at pinned revision | All 1,000 train examples fit; 835–932 tokens per rendered prompt/completion; non-thinking chat prefix matched |

The ML test constructs a tiny random Qwen3 model locally, checks that prompt labels are
masked, performs one real optimizer step, verifies LoRA weights changed, saves the
adapter, and reloads it. It downloads no pretrained weights and supplies no extraction
benchmark result.

The Python run emitted a Starlette/httpx deprecation warning and a PEFT warning about
the random test model's missing upstream config location. Neither affected assertions.
Desktop and mobile test screenshots were inspected; the README image is an actual
CPU-demo capture, not a mockup.

**Not executed:** pretrained Qwen extraction benchmarks, GPU LoRA/QLoRA training,
Unsloth runtime, Docker image builds/runtime, and remote GitHub Actions. Docker is not
installed locally. CI configuration includes CPU container smoke tests and a separate
random-weight ML integration job, but this record does not claim those remote jobs ran.
