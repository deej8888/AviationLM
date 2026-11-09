# AeroLM model / adapter card

**Release status:** completed experimental CPU LoRA training and evaluation on November 8,
2026 (America/New_York). A trained adapter exists locally; weights are not bundled or
uploaded. Reports, raw predictions, and a completed run manifest are committed.
The adapter underperforms rules on the authored challenge set and requires human review.

## Intended use

Extract draft charter-request facts from synthetic English messages into the v1 Pydantic
contract, for human review. This is not a dispatcher, quotation engine, flight-planning
system, or source of airworthiness, legality, performance, or crew-duty decisions.

## Base models and licenses

Default: [Qwen/Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B).
Supported configuration alternative: [Qwen/Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B).
Both model cards declare Apache-2.0. Repository code is Apache-2.0 and bundled synthetic
data is CC0-1.0. Retain upstream model notices when redistributing weights.

## Training recipe

Three epochs; rank-16 LoRA with alpha 32 and no dropout; attention q/k/v/o projections
and MLP gate/up/down projections; 2e-4 learning rate; cosine schedule; 5% warmup;
batch size 1 with gradient accumulation 8; sequence length 3,072. Only completion
tokens contribute to the loss. Packing is disabled. Thinking is disabled consistently
in training prompts and inference. Oversized examples raise an error instead of silently
truncating labels. QLoRA uses NF4 double quantization and bf16 when the GPU supports it,
otherwise fp16. Unsloth is an optional, explicitly selected Linux acceleration path.

The completed CPU experiment used `configs/cpu-lora.toml`: the same LoRA recipe with a
1,024-token sequence limit, BF16, 12 CPU threads, no quantization, and no gradient
checkpointing. It used Qwen3-0.6B revision
`c1899de289a04d12100db370d81485cdf75e47ca`, seed 42, 1,000 synthetic training requests,
120 validation requests, three epochs, and 375 optimizer steps. The Ryzen 9 9950X run
trained 10,092,544 parameters in 6,876.6 seconds (114.6 minutes). GPU recipes and Unsloth
remain unexecuted. See the [completed manifest](../benchmarks/runs/qwen3-0.6b-cpu-lora.json).

Default configs pin an immutable base revision, which is resolved and verified before training. The saved run
manifest contains the resolved base revision, config, dataset manifest, dependency
versions, Python/CUDA/GPU details, resume checkpoint, and training status. Dependency
resolution is locked, but bit-identical GPU weights are not guaranteed across hardware,
CUDA kernels, or driver versions. Pin `revision` to the recorded SHA for repeat runs.

## Inference and evaluation

The base and adapter backends use the same prompt/schema, non-thinking mode, greedy
decoding, and output-token budget. Greedy decoding is chosen for repeatable extraction
benchmarks; it is not a claim of optimal Qwen generation quality. The adapter loader
requires a completed AeroLM manifest, verifies base model identity, and loads its recorded
base revision. It also rejects a domain or schema/prompt hash that differs from training.
Invalid JSON or schema-invalid output is rejected; no model output is
silently repaired and no rules fallback hides a failed model run.

Report base-versus-adapter precision, recall, F1, strict JSON validity, schema validity,
and exact-record accuracy on the same held-out input. Include dataset/prompt hashes,
raw predictions, full run metadata, and adapter hashes. Do not fill in scores before
actually running evaluation. See [measured results](../benchmarks/README.md) for all runs.

The completed adapter scored 99.7358% micro F1 and 96.6667% exact-record match on the
120-request generated holdout, with 100% JSON/schema validity. On the independent
24-request synthetic challenge it scored 64% F1, 100% JSON validity, 75% schema validity,
and 0% exact-record match. Rules achieved 94.5313% F1 and 70.8333% exact match on that
challenge. Both base-model suites scored zero under the strict raw-output contract,
primarily because every output used Markdown fences; the base also made schema/fact
errors. These results do not establish reliability on real company emails.

## Known limitations

Valid JSON can still contain unsupported or wrong facts. Review warnings are deterministic
completeness checks, not a calibrated confidence estimate or proof of semantic grounding.
Prompt injection cannot be assumed solved by instructions. Rules mode misses examples
with reordered dates, spelled-out passenger counts, suffix-form budgets, and some negations.
Airport identifiers are checked for shape, not looked up in an authoritative directory.
IATA/ICAO aliases are not resolved. Dates are not timezone-converted. Synthetic evaluations
do not establish reliability on actual aviation operations or customer email.

The completed adapter frequently invents missing times, timezones, aircraft preferences,
trip types, and contact addresses on sparse requests. It can emit `"null"` as a literal
string, omit later itinerary legs, and fail airport/time normalization. All training
examples include a contact address and mostly supply other fields, so the generated
holdout does not measure robustness to missing information. JSON/schema validation
does not catch every unsupported fact. The adapter is not ready for unattended use.

Any future weight release should include the completed manifest, upstream notices, adapter
license, failure analysis, and measured reports. Improve data coverage and reserve a new
untouched evaluation set before making broader quality claims. No proprietary company
information was used in this experiment.
