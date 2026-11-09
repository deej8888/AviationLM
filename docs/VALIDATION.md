# Local validation record

Executed November 8, 2026 on Windows with Python 3.12.13, Node 24.18.0,
uv 0.11.32, and the committed dependency locks.

| Check | Observed result |
| --- | --- |
| `uv run --no-sync pytest` with ML/structured dependencies installed | 55 passed |
| `uv run --no-sync python scripts/verify_benchmarks.py` | All 11 reports audited: rules regenerated; stored model outputs rescored; aggregate/per-request counts and dataset/prompt hashes matched |
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

After publication, [GitHub Actions run 42504287236](https://github.com/deej8888/AviationLM/actions/runs/42504287236)
completed successfully: all three Python jobs, ML smoke test, dashboard tests/build,
and CPU container build/runtime smoke tests passed. Docker remains unavailable locally.

The real pinned Qwen3-0.6B checkpoint was trained with CPU BF16 LoRA on 1,000 synthetic
requests for three epochs (375 optimizer steps, 114.6 minutes of training). Base and
adapter evaluations completed on 120 generated test requests and 24 unchanged challenge
requests, with matching model/prompt/data/decoding/inference settings. Every saved Qwen
prediction was replayed through the evaluator and reproduced aggregate and per-field
scores exactly. Reported adapter hashes match the completed local training files.

The adapter scored 99.7358% F1 on generated requests and 64% F1 on the challenge, where
it produced 100% JSON validity, 75% schema validity, and 0% exact-record match. It remains
weaker than rules on the challenge. See `benchmarks/README.md` for the full measured
table and failure analysis; low training loss is not evidence of operational accuracy.

The first adapter evaluation process stopped after 99/120 generated requests without
writing a completed report. The saved training and completed base reports were retained;
the entire unfinished generated suite was rerun before the final challenge evaluation.
No partial output was counted as a completed benchmark.

The runner's real adapter-backed demo extraction passed schema validation with human
review required, and `--activate` selected that adapter in the ignored local `.env`.
This exercises the extraction service directly; it does not establish real-world accuracy
or verify an already-running HTTP server has reloaded its configuration.

**Not yet executed:** GPU LoRA/QLoRA training and Unsloth runtime. No real-world email
evaluation or production deployment was performed. Weights remain local.

## Second experiment validation

The 240-example, one-epoch v2 pilot completed training and all five validation runs
(rules, raw base, prompted/constrained base, original adapter, new adapter). Exact inputs,
training manifest/config, reports, and raw outputs are committed. The new adapter scored
95.9128% F1 and 19/24 exact requests on those new validation cases; it still had one
schema failure. The 300-request test set was not evaluated and full v2 training did not run.

Generator 2.0 had process-dependent evidence-list ordering. Version 2.1 sorts it;
cross-process tests use different Python hash seeds, and another test verifies that
archived pilot emails/labels match the current generator. Frozen source bytes and
historical hashes are retained rather than silently changing the original run record.

New checks cover dataset omissions/ledgers, strict evidence rejection, contradictory
mentions, few-shot prompting, null-slot metrics, experiment locking, and frozen adapter
metadata. A real tiny random model also generates JSON through the constrained decoder
without downloads. This supplies no extraction benchmark score.

Next.js production build/TypeScript checks and all eight desktop/mobile browser tests
passed. The benchmark table's new metrics and mobile horizontal scrolling were checked;
desktop/mobile screenshots were inspected. Browser tests use isolated ports and an
explicit rules backend, independently of a developer's activated adapter. The updated
GPU dependency export succeeded; Docker/GPU runtime remains untested locally.
