---
license: apache-2.0
library_name: peft
base_model: Qwen/Qwen3-0.6B
language: en
tags:
  - aviation
  - information-extraction
  - lora
  - synthetic-data
---

# AeroLM Qwen3 0.6B charter adapter v2

This is an experimental LoRA adapter for extracting structured charter-flight
requests into AeroLM's JSON schema. It requires the Qwen3 0.6B base model and
the matching AeroLM prompt and schema. The adapter does not book flights.
Review all outputs against the original request before operational use.

- Base: `Qwen/Qwen3-0.6B`, revision `c1899de289a04d12100db370d81485cdf75e47ca`.
- Training: 2,000 generated fictional requests, three epochs, CPU bfloat16,
  750 steps, about 3 hours 54 minutes; rank 16 LoRA, 10,092,544 trainable parameters.
- Dataset: synthetic CC0 examples; no proprietary company data. Generated
  labels were checked programmatically and not independently reviewed by a human.
- Adapter SHA-256: `1666afd8f0ace070ac46c0a18dae8c9865404d2d432cf00c92af356aa3568a63`.
- Code, training methodology, and raw benchmark predictions:
  [github.com/deej8888/AviationLM](https://github.com/deej8888/AviationLM).

## Evaluation

| Frozen synthetic test | Field F1 | JSON valid | Schema valid | Exact requests |
| --- | ---: | ---: | ---: | ---: |
| Generated test (300 requests) | 98.57% | 100% | 99% | 284/300 |
| Separately authored test (50 requests) | 92.27% | 100% | 94% | 35/50 |

The 300-request set shares the generator and vocabulary with training. The
50 fictional requests were authored separately from the training generator,
but neither their labels nor the training labels have independent human review.
Neither set establishes performance on real emails. On the 50-request set,
the rules baseline achieved 90.91% F1 and 26/50 exact. Failure examples include
multi-leg itineraries, airport-code transcription, and midnight conversion.
When a response fails schema validation, this evaluator counts its expected
fields as missed rather than scoring individual facts in the invalid output.
Exact match requires every field to match. These are small diagnostic samples.

## Use with AeroLM

Clone the project and install its ML dependencies as described in its README.
Download this repository's adapter files, then configure the local API. In a
Python shell in the project directory:

```python
from huggingface_hub import snapshot_download

path = snapshot_download("deej8888/AeroLM-Qwen3-0.6B-charter-v2")
print(path)  # set AEROLM_ADAPTER_PATH to this directory
```

Set `AEROLM_BACKEND=hf` and `AEROLM_ADAPTER_PATH` to the printed directory;
`AEROLM_MODEL_ID` defaults to the required base model. The adapter manifest pins
the base revision and checks compatibility with the original prompt and schema.
Model weights and ML dependencies are downloaded separately. See the project
README for CPU and GPU configuration.

This is research software. Airport references can be incomplete or stale;
source matching, schema validity, and reference checks do not establish truth,
airport availability, operational suitability, or flight safety.
