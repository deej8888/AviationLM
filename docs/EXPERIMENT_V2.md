# Second experiment: missing information and generalization

The first adapter achieved 99.74% F1 on generated requests but 64% on the authored
challenge. All 1,000 training examples supplied a time, timezone, aircraft preference,
trip type, and contact address. None contained multiple legs. The challenge exposed
unsupported values and poor handling of sparse requests. Data coverage is a strong
hypothesis to test; this experiment does not assume that a new adapter will beat rules.

## What changed

- A separate version-2 generator samples missing facts **before rendering text**. It
  includes complete, partial, ambiguous, negated, corrected, multi-leg, unknown-aircraft,
  and empty requests. Version 1 and every published result remain unchanged.
- Every non-null gold fact has a construction-ledger quote. Automated checks reject
  missing quotes or labels that disagree with the ledger. This catches bookkeeping
  errors; it does not replace independent annotation review.
- Reports include per-scenario counts, extra/missing facts in raw prediction logs,
  and explicit null-slot false fills. Full-request accuracy and schema validity are
  visible in the dashboard alongside F1 and JSON validity.
- A stronger base-model baseline uses two separately authored synthetic demonstrations
  and optional constrained generation. Its reports have their own actual prompt hash
  and decoding metadata. Its improvement must not be attributed to LoRA.
- API results include source-mention evidence and warnings without silently rewriting
  extracted values. Strict rejection is optional. Raw model benchmarks bypass these
  checks and receive no repair or rules fallback.

## Data and experiment boundaries

The full dataset contains **2,000 train / 200 validation / 300 test** requests, seed 84.
Training contains 200 multi-leg cases, 200 empty cases, and 998 missing contact addresses.
It omits 658 leg times and 847 leg timezones. Train/validation/test use disjoint wrapper
families; the underlying clause renderer and much vocabulary are shared. The test split
also includes four airport-code tokens absent from training. This remains a controlled
synthetic benchmark, not a sample of real operational email.

All data is invented CC0 text; addresses use `.example`. Aircraft/category pairs use the
existing illustrative catalog, while fictional `ExampleAir` preferences have an unknown
category. Relative or format-ambiguous dates stay null. A correction explicitly supersedes
the earlier passenger count. Multi-leg targets preserve source order. Gold labels come
from sampled facts, never from rules extraction or model predictions.

No independent human annotation review has been performed. The generator and tests were
developed together; the new test set is held out from model training and pilot selection,
but should not be described as independently authored or representative production data.

Generator 2.1 canonicalizes evidence ordering across Python hash seeds while retaining
the 2.0 sampled emails and labels. The first completed pilot used 2.0; its exact inputs
are archived in [`data/experiments/v2-pilot`](../data/experiments/v2-pilot/) rather than
rewriting its recorded hashes. New staged runs default to `artifacts/robust-v2.1`.

## First measured pilot

Completed November 8, 2026 (America/New_York), on the same Ryzen CPU as the original run.
Training used 240 examples for one epoch, 30 optimizer steps, and 453.1 seconds
(7.55 minutes), excluding generation-based benchmarks. Every row below uses the **same 24 new validation
requests**. These are not the original authored challenge cases.

| Variant | Precision | Recall | F1 | JSON valid | Schema valid | Exact request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Rules | 94.56% | 73.94% | 82.99% | 100% | 100% | 3/24 |
| Raw base Qwen | 0% | 0% | 0% | 0% | 0% | 0/24 |
| Base + two demonstrations + constraints | 64.04% | 77.66% | 70.19% | 100% | 95.83% | 0/24 |
| Original v1 adapter | 74.47% | 55.85% | 63.83% | 95.83% | 54.17% | 3/24 |
| New v2 pilot adapter | 98.32% | 93.62% | 95.91% | 100% | 95.83% | 19/24 |

The pilot adapter had zero false fills across 111 explicit null slots in its 23
schema-valid responses. The original adapter had 30/56, rules had 2/117, and the
prompted/constrained base had 43/115. Those denominators differ because schema-invalid
responses are excluded; this is **not** evidence of zero hallucinations on all requests.
The new adapter still made three wrong-value predictions and missed 12 facts under
the strict scoring protocol.

Observed remaining failures were Citation XLS category classification (two requests),
AM/PM conversion (one schema failure and one wrong time), and a missed pet requirement.
Constrained base generation also emitted a non-ISO date: JSON Schema `format` hints and
Pydantic validators are not all enforced by the decoding library. Pydantic rejected it.

This supported further investigation of data coverage. The small validation sample,
shared clause renderer, different training sizes/epochs/seeds, and inspection of these
errors prevent a broad generalization or single-cause claim. The full run below used a
fresh adapter and a separate 300-request test.

Reports and raw outputs are in [`benchmarks/results`](../benchmarks/results/) with the
`v2-pilot-` prefix. The exact [training manifest](../benchmarks/runs/v2-pilot-training.json)
and [pilot config](../benchmarks/runs/v2-pilot-config.toml) are committed. To repeat this
historical training recipe in a new output directory:

```sh
uv run --no-sync aerolm train --config benchmarks/runs/v2-pilot-config.toml --data data/experiments/v2-pilot --output artifacts/repeated-v2-pilot
```

The completed local pilot adapter is `artifacts/robust-v2/pilot/adapter`. To test it
without changing the saved default, set `AEROLM_ADAPTER_PATH` to that path for a new API
process, keeping model revision, CPU BF16, and 12 threads consistent with the run.

## Completed full run and frozen test

The full v2 run finished on November 10, 2026 (America/New_York). It trained Qwen3-0.6B
with rank-16 CPU LoRA, BF16, 12 CPU threads, 2,000 synthetic requests, three epochs,
and 750 optimizer steps. Training took **14,039.7 seconds (3 hours 54 minutes)**;
the five validation evaluations and three test evaluations were additional. The
candidate, config, data manifest, and validation report hashes were frozen before test.

| Run / split | N | Precision | Recall | F1 | JSON valid | Schema valid | Exact request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Rules / validation | 200 | 92.20% | 70.54% | 79.93% | 100% | 100% | 39/200 |
| Original v1 adapter / validation | 200 | 76.34% | 57.36% | 65.51% | 97% | 57.5% | 25/200 |
| New v2 adapter / validation | 200 | 100% | 100% | 100% | 100% | 100% | 200/200 |
| Rules / test | 300 | 93.14% | 68.59% | 79.00% | 100% | 100% | 63/300 |
| Raw base Qwen / test | 300 | 0% | 0% | 0% | 0% | 0% | 0/300 |
| New v2 adapter / test | 300 | 99.36% | 97.79% | 98.57% | 100% | 99% | 284/300 |

All 300 base-model test responses used Markdown fences, so strict raw JSON parsing
rejected them. This interface score does not mean the base recognized no facts. The
original v1 adapter was evaluated on the 200-request validation set, not the 300-request
test; do not compare its validation score to the v2 test as a matched test result.

The v2 test produced 2,344 correct facts, 15 wrong-value false positives, and 53 missed
facts under the strict scoring protocol. Three schema-invalid responses receive no fact
credit. Among the 297 schema-valid outputs, the null-slot diagnostic found 0 false fills
across 1,452 explicitly null slots. This excludes invalid responses and does not imply
zero hallucinations: 13 schema-valid requests contained wrong airport-code values.

All **16 non-exact test requests** included lowercase airport codes absent from training.
Examples included truncating `KLAX` to `KLA` and producing `KBOB` for `KBOS`. The three
schema failures emitted `KSFo` rather than uppercase `KSFO`. These are meaningful errors:
code shape validation alone does not verify an airport. The test uses disjoint wrapper
families and includes four held-out airport-code tokens, but shares its clause renderer
and much of its vocabulary with training. It is synthetic and has not been independently
human-reviewed; neither its high score nor the perfect validation score establishes
reliability on company email or operational decisions.

Reports and raw predictions use the `v2-full-` and `v2-test-` prefixes in
[`benchmarks/results`](../benchmarks/results/). Exact metadata is in the
[training manifest](../benchmarks/runs/v2-full-training.json),
[data manifest](../benchmarks/runs/v2-full-data-manifest.json),
[config](../benchmarks/runs/v2-full-config.toml), and
[frozen selection](../benchmarks/runs/v2-full-selection.json). The selection records
the original local report paths; their bytes were copied into the benchmark directory.
The local full adapter is `artifacts/robust-v2.1/full/adapter`; weights are not bundled.

After the run, an adapter-backed FastAPI smoke request returned the correct TEB-to-MIA
route, date, time, passenger count, and null missing fields, with human review required.
The local `.env` was updated to use the full adapter after that check. Existing API
processes need a restart. The staged experiment runner itself does not auto-activate models.

## Run the staged experiment

Run from the repository root. The native CPU profile requires efficient BF16 support;
select float32 on CPUs that lack it. No GPU, cloud bill, or hosted API is required.

```sh
uv sync --frozen --extra dev --extra ml --extra structured

# Data generation only; no model download or training.
uv run --no-sync python scripts/run_v2_experiment.py --stage prepare

# 240 training requests, one epoch (30 optimizer steps), 24 validation requests.
uv run --no-sync python scripts/run_v2_experiment.py --stage pilot

# Inspect durable progress from another terminal.
python scripts/experiment_status.py --output artifacts/robust-v2.1
```

The pilot trains a fresh adapter from the pinned pretrained checkpoint, not from the
first AeroLM adapter. It evaluates rules, raw base Qwen, the base with demonstrations
and constrained decoding, and raw v2 Qwen on the **same 24 validation requests**. If
`artifacts/full-cpu/adapter` exists, it also evaluates the original adapter on those
validation requests. Pass `--previous-adapter` to select another local v1 location.

The pilot never evaluates either generated test file or the published 24-case challenge.
Its small validation sample is for development and throughput checks. One epoch on 240
requests is not comparable training compute to the original three-epoch, 1,000-request
run; use the new same-input comparison to diagnose behavior, not to claim causality.

Reports and raw outputs go to `artifacts/robust-v2.1/pilot/validation-reports/`, with a
`pilot-summary.json` and a protocol-checked raw-base/raw-adapter comparison. Completed
training and compatible reports are reused on restart; interrupted training resumes a
checkpoint if present. An OS lock prevents simultaneous writers in one experiment root.
An interrupted evaluation is rerun in full and never counted as completed.

After selecting settings on validation, the remaining commands are:

```sh
# Fresh adapter, full 2,000-request dataset, three epochs (750 optimizer steps).
uv run --no-sync python scripts/run_v2_experiment.py --stage full

# Only after full validation: evaluate the frozen candidate on the 300 test requests.
uv run --no-sync python scripts/run_v2_experiment.py --stage test
```

Full validation writes `selection.json` with hashes of the config, dataset manifest,
adapter weights/config/training manifest, and completed validation reports. Test scoring refuses changed inputs.
Freezing records an experiment candidate; it is not a production qualification. Do not
repeatedly tune against test results. Use a new test set for a later iteration.

The runner does not change `.env`, replace the original adapter, publish weights, or
activate a candidate automatically. Historical reports remain in `benchmarks/results/`.

## Separate baseline and inference controls

```sh
uv run --no-sync aerolm evaluate --backend hf --device cpu --precision bfloat16 --cpu-threads 12 --revision c1899de289a04d12100db370d81485cdf75e47ca --few-shot data/charter_demonstrations.jsonl --structured --dataset artifacts/robust-v2.1/pilot/data/validation.jsonl --output artifacts/prompted-base.json
```

Omit `--structured` to measure demonstrations alone, or omit both options for the raw
zero-shot baseline. Comparison rejects different prompt hashes or decoding modes.
The [LM Format Enforcer Transformers integration](https://github.com/noamgat/lm-format-enforcer)
filters allowed tokens during generation. Unsupported constraints, token limits, and
model mistakes can still cause validation failure; Pydantic remains the acceptance gate.
Formatting constraints do not establish factual accuracy.

For the API, `AEROLM_FEW_SHOT_PATH` and `AEROLM_STRUCTURED_OUTPUT=true` select those modes.
They are opt-in and require the relevant dependencies.

## Source evidence in the API

`evidence` contains a path, candidate value, `matched`/`unverified` status, source quote,
character offsets, and matching method. Airports and email-shaped contacts use literal mentions; dates,
times, and small word-form passenger counts support deterministic normalization.
Aircraft categories can use the small illustrative catalog.

`AEROLM_EVIDENCE_POLICY=warn` is the default. Unrecognized evidence produces a warning
while preserving the model output for review. `reject` returns an extraction failure
when a non-null fact lacks a recognized mention; unfamiliar but correct wording can
therefore be rejected. No missing value is filled by this checker.
Common negated service mentions and conflicting passenger counts are flagged for review;
the checker conservatively flags both counts even when an explicit correction is present.

**A mention is not proof of the extracted fact.** The checker does not reliably bind
mentions to itinerary roles, resolve conflicting threads, or verify negation. Requirement
evidence explicitly identifies itself as mention-only. A fabricated value that also
appears elsewhere in a message can pass a mention check. Every result still requires
human review; these checks are not confidence scores or a safety guarantee.

Other industries can register their own optional `DomainSpec.evidence` function without
changing the extraction engine. The prompt/schema hash remains unchanged by adding a
review function, so the original adapter remains loadable.

## Measures to use when selecting the next run

Inspect exact-request accuracy, precision, extra facts, schema validity, and per-scenario
results together. The null-slot false-fill rate is the number of non-null predictions
in explicitly null gold slots divided by gold null slots in **schema-valid responses**.
Invalid responses are excluded from this diagnostic denominator and must be assessed
through validity and the existing all-request F1. Empty arrays and entirely extra legs
are covered by false positives, not by the bounded null-slot diagnostic.

Keep rules as a measured baseline. A candidate should reduce unsupported values without
losing valid facts, and improve complete-request accuracy on a sufficiently broad,
independently reviewed evaluation before any operational use. No improvement percentage
or production-readiness claim is assumed in advance.
