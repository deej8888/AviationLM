# Benchmark log

The committed numbers were **actually computed locally on November 8, 2026
(America/New_York)**. The Qwen3-0.6B LoRA run completed on CPU; no GPU fine-tuning
was performed. The rules backend is a hand-written pattern baseline, not an LM.

| Run | N | Precision | Recall | F1 | JSON validity | Schema validity | Exact record |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rules-generated` | 120 | 99.9338% | 99.6697% | 99.8016% | 100% | 100% | 95.8333% |
| `rules-challenge` | 24 | 98.3740% | 90.9774% | 94.5313% | 100% | 100% | 70.8333% |
| Qwen3-0.6B base / generated | 120 | 0% | 0% | 0% | 0% | 0% | 0% |
| Qwen3-0.6B base / challenge | 24 | 0% | 0% | 0% | 0% | 0% | 0% |
| Qwen3-0.6B + CPU LoRA / generated | 120 | 99.7358% | 99.7358% | 99.7358% | 100% | 100% | 96.6667% |
| Qwen3-0.6B + CPU LoRA / challenge | 24 | 54.1667% | 78.1955% | 64.0000% | 100% | 75% | 0% |

Machine-readable reports and raw predictions: [`results/`](results/).
Each report records the dataset SHA-256, sample count, prompt hash, package versions,
platform, generation configuration, per-field metrics, and runtime latency. Latencies
are measured after model loading and are not intended as cross-machine comparisons.

The Qwen base run used pinned revision `c1899de289a04d12100db370d81485cdf75e47ca`,
BF16 inference on the Ryzen CPU, 12 threads, non-thinking mode and greedy decoding.
Every raw response contained Markdown fences; examples also copied schema constraints
as values, invented requirements, and put extra fields inside legs. Strict validation
rejected the outputs. The zero score is an interface-contract result, not evidence that
no individual aviation facts were recognized. No repair was performed.

The adapter used the same inference protocol. Training used 1,000 synthetic requests,
120 validation requests, three epochs, rank-16 LoRA, and 375 optimizer steps. Actual
training runtime was 6,876.6 seconds (114.6 minutes), with 10,092,544 trainable parameters.
The [completed manifest](runs/qwen3-0.6b-cpu-lora.json) includes config and data hashes,
dependencies, and hardware metadata; [comparisons](runs/qwen3-0.6b-cpu-lora-comparison.json)
contain exact base-versus-adapter deltas. Weights remain local and are not bundled.

| Qwen run | Median request latency | Mean request latency |
| --- | ---: | ---: |
| Base / generated | 9.15 s | 9.41 s |
| Base / challenge | 8.48 s | 8.37 s |
| Adapter / generated | 6.72 s | 6.71 s |
| Adapter / challenge | 5.54 s | 5.52 s |

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

The adapter matched 116/120 generated requests exactly. Its four errors were one route
copied into the aircraft preference and three contact addresses with a duplicated
`desk` prefix. On the independent challenge, all 24 outputs were JSON objects, but only
18 passed the schema, and **0/24 matched the complete expected record**. Across the
full challenge, scoring counted 104 correct facts, 88 false positives, and 29 omissions;
schema-invalid outputs receive no fact credit.
Frequent unsupported details included a departure time, timezone, aircraft/category,
trip type, and fabricated contact such as `user@example.com` or the string `"null"`.
Other failures included losing the second itinerary leg, lowercase airport codes,
city names in airport fields, and invalid 12-hour times.

The training data mostly supplies those fields and always supplies a contact address;
the sparse challenge exposes that coverage gap. This supports improving the data
distribution before further training. It does not establish which change will fix
generalization. Preserve these published cases as a diagnostic set and add a new
untouched evaluation set for the next iteration. The current adapter is less accurate
than rules on this challenge despite its improvement over the strict base-model score.

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

Reproduce the full CPU experiment with `scripts/run_local_experiment.py` as documented
in the root README, then use `aerolm compare` to calculate deltas. Saved raw predictions
from all four Qwen reports were replayed through the evaluator: dataset/prompt hashes,
aggregate scores, and per-field counts matched exactly; the adapter file hash matched
the completed local run. This audit recomputes scores without regenerating model output.
The separate CPU random-weight optimizer smoke test is an integration check and
contributes no extraction score to this table.
