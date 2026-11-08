# AeroLM model / adapter card

**Release status:** training implementation and CPU demonstration; no trained adapter
or fine-tuned model weights are bundled. No model benchmark is claimed.

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
actually running evaluation. See `benchmarks/README.md` for measured rules results.

## Known limitations

Valid JSON can still contain unsupported or wrong facts. Review warnings are deterministic
completeness checks, not a calibrated confidence estimate or proof of semantic grounding.
Prompt injection cannot be assumed solved by instructions. Rules mode misses examples
with reordered dates, spelled-out passenger counts, suffix-form budgets, and some negations.
Airport identifiers are checked for shape, not looked up in an authoritative directory.
IATA/ICAO aliases are not resolved. Dates are not timezone-converted. Synthetic evaluations
do not establish reliability on actual aviation operations or customer email.

Before releasing a trained adapter, publish its actual model card, base revision, dataset
manifest, training hardware/time, adapter license, validation methodology, failure analysis,
and measured reports. This template is not evidence of a completed training run.
