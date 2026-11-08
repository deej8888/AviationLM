# Security and operational boundaries

This is a local development/research application. The API does not store request bodies
or log message contents. The dashboard stores its state in memory and exports JSON only
when requested. No external inference API is called. HF mode downloads the selected public
model once; cached runs can use Hugging Face offline settings. Fonts are bundled locally.

The default Compose ports bind to loopback. Optional `AEROLM_API_KEY` protects the inference
API with bearer authentication. The Next.js proxy holds that token server-side, so the
token does **not** authenticate dashboard visitors. Add dashboard authentication, TLS,
rate limits, ingress body limits, and request deadlines before hosting for other users.
Do not expose the development server or unauthenticated proxy publicly.

Inference is bounded to one active request per API process; busy requests receive 503.
Each additional worker loads another copy of the model. JSON/schema failures return 502
without exposing raw model output. Oversized text is rejected, and model inputs that
exceed the token limit are rejected rather than truncated. The benchmark runner stores
raw predictions only for explicitly declared synthetic fixtures.

Schema validation verifies structure, not truth. Human review is always required. No
actual booking, dispatch, maintenance, procurement, or crew assignment actions exist.

To report a vulnerability before a public repository has a private reporting channel,
contact the repository maintainer privately through their published profile. Do not
include private aviation documents in a public issue. Configure GitHub private vulnerability
reporting when publishing the repository.
