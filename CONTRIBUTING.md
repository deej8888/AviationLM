# Contributing to AeroLM

Start with an issue describing a reproducible extraction failure, dataset improvement,
or narrowly scoped extension. Include a **synthetic** request, expected JSON, and a test.
Never paste proprietary emails, company code, client itineraries, or identifying details.

```sh
uv sync --frozen --extra dev
uv run pytest
uv run python scripts/verify_benchmarks.py
cd web
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

Use Python 3.12 and Node 24 for the reference environment. GPU training is separate from
the CPU demo. For an optional real ML smoke test, install `--extra ml --extra dev` and run
`uv run --no-sync pytest -m ml`. The smoke test uses random tiny weights, not Qwen3-0.6B
pretrained weights, and its training loss is not an extraction benchmark.

Keep prompts, schemas, data manifests, and evaluation reports in sync. When extraction
behavior changes, rerun benchmarks and review per-example predictions. Explain score
changes; do not tune against the challenge set and describe it as an untouched holdout.
Never add made-up benchmark numbers or claim an unexecuted training run.

By contributing code you agree to Apache-2.0 licensing. Original synthetic fixtures should
be dedicated under CC0-1.0. Public third-party data needs an explicit license, attribution,
and documented provenance before adding a new ingestion path.
