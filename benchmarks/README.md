# Benchmark log

The committed numbers were **actually computed locally on November 8, 2026**. No pretrained
Qwen extraction evaluation or GPU fine-tuning was performed. The rules backend is a
hand-written pattern baseline, not an LM.

| Run | N | Precision | Recall | F1 | JSON validity | Schema validity | Exact record |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rules-generated` | 120 | 99.9338% | 99.6697% | 99.8016% | 100% | 100% | 95.8333% |
| `rules-challenge` | 24 | 98.3740% | 90.9774% | 94.5313% | 100% | 100% | 70.8333% |
| Qwen3 base | — | Not run | Not run | Not run | Not run | Not run | Not run |
| Qwen3 + adapter | — | Not run | Not run | Not run | Not run | Not run | Not run |

Machine-readable reports and raw predictions: [`results/`](results/).
Each report records the dataset SHA-256, sample count, prompt hash, package versions,
platform, generation configuration, per-field metrics, and runtime latency. Latencies
are measured after model loading and are not intended as cross-machine comparisons.

## Protocol

1. Use the same dataset, schema/prompt, base revision, and decoding configuration for
   base-versus-adapter evaluation. `aerolm compare` refuses mismatches.
2. Generate **raw** model output, without JSON repair or rules fallback.
3. Measure strict JSON-object validity; duplicate keys, fences, trailing prose, NaN, and
   non-object roots are invalid.
4. Validate against the Pydantic schema separately. Invalid-schema outputs receive no
   slot credit, even if JSON is syntactically valid.
5. Flatten non-null facts to `(field path, exact JSON value)`. Requirements are unordered;
   itinerary legs preserve their index. Ignore the constant routing discriminator.
6. Count micro TP / FP / FN across examples. An incorrect non-null value contributes
   one FP and one FN. Missing/null fields count only as omissions when a gold fact exists.
   There is no true-negative credit for unused slots.
7. Exact-record match requires schema validity and equality of all non-null facts.

Precision = TP / (TP + FP), recall = TP / (TP + FN), and F1 is their harmonic mean.
Zero denominators return zero. Runtime/model-loading failures abort a run, rather than
being hidden as scored parsing failures. Predictions identify every sample for auditing.

## Interpretation and observed failures

The generated set shares a small controlled vocabulary with rules, although its phrasing
families are held out. It is a reproducibility fixture, not a realistic generalization
estimate. Perfect rules JSON validity follows from Pydantic serialization.

The independent challenge set reveals misses on lowercase airport identifiers, departure
details placed before the route, word-form passenger counts, labeled origin/destination
fields, suffix-form budget currency, and custom services. Postposed negation such as
"Catering is not required" can produce a false-positive service. The rules baseline is
deliberately limited; it is not tuned to erase every published challenge failure.

A high aggregate F1 can coexist with materially lower exact-request accuracy. Never use
either synthetic score as evidence that a quote, dispatch, aircraft assignment, or
maintenance/crew decision is safe. Unknowns and warnings still need human confirmation.

## Reproduce and verify

From repository root:

```sh
uv run aerolm generate
uv run aerolm evaluate --dataset data/generated/test.jsonl --output artifacts/rules-generated.json --label rules-generated
uv run aerolm evaluate --dataset data/charter_challenge.jsonl --output artifacts/rules-challenge.json --label rules-challenge
uv run python scripts/verify_benchmarks.py
```

The verifier regenerates data in a temporary directory and compares exact scores,
dataset metadata, per-field counts, and prompt hash with committed reports. Timestamps,
environment metadata, and latency are intentionally excluded from equality checks.

After an actual training run, evaluate base and adapter on the same immutable base SHA,
publish both reports and raw predictions, and use `aerolm compare` to calculate deltas.
Until then, model results remain **not run**. The CPU random-weight optimizer smoke test
is an integration check and contributes no extraction score to this table.
