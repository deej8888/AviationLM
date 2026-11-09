# AeroLM charter data card

The original version-1 generator and published benchmark inputs remain unchanged.
The separate [v2 experiment](EXPERIMENT_V2.md) adds a 2,000/200/300 dataset with missing
fields, corrections, negation, multi-leg requests, empty requests, and a gold evidence
ledger. `aerolm generate-v2` writes that profile to a new directory and refuses to
overwrite an existing versioned dataset. Its construction ledger and tests are automated
checks, not independent human annotation. The sections below describe version 1.

**Version:** 1.0 · **License:** CC0-1.0 · **Source:** entirely invented, programmatic text.

No company inboxes, customer itineraries, internal SOPs, proprietary code, private contact lists,
or scraped documents are used. Contact addresses use the reserved `.example` namespace.
Airport and aircraft names are illustrative public terminology, not an operational airport
database or aircraft performance specification.

## Composition and splits

`aerolm generate` writes 1,000 train / 120 validation / 120 test examples by default. Each
record contains `id`, `split`, `template_family`, `text`, `expected`, `provenance`, and
`license`. Ground truth comes from sampled structured facts before rendering the text;
the rules extractor never supplies the labels.

The generator samples 12 airport identifiers, eight named aircraft preferences, one-way
and round-trip requests, explicit ISO/long-form dates, UTC/local departure times, passenger
counts, budgets, contact emails, and normalized service requirements. Periodic examples
remove passenger counts, use relative dates, and replace an origin with an ambiguous city.
Relative dates have no reference date and remain null. Five training phrasing families,
two validation families, and three test families are disjoint. Exact text duplicates across
splits are rejected. Airports and vocabulary intentionally overlap; this is a template
holdout, **not** a geography or vocabulary holdout.

`data/charter_challenge.jsonl` contains 24 separately authored cases, including multi-leg
requests, AM/PM and Zulu time, ambiguous cities and numeric dates, negation, lowercase
codes, word-form passenger counts, reordered fields, custom requirements, and an injected
instruction. Its labels are specified independently in `scripts/create_challenge.py`.
It is a small diagnostic suite, not a statistically representative sample.

## Reproducibility

Python's local `random.Random` instance is seeded by generator version, seed, and split.
Output uses UTF-8 and LF line endings, independent of host platform. `manifest.json`
records counts, seed, template families, generator version, and SHA-256 of every split.
Training verifies train/validation hashes and rejects overlap. Test data is not passed
to the trainer. `scripts/verify_benchmarks.py` rebuilds the test split in a temporary
directory and checks committed scores and data hashes.

## Limits and next data work

English only. The generator uses a deliberately small vocabulary and mostly explicit
slot wording. Its training set does not yet teach multi-leg or email-thread correction
handling; those appear in diagnostic evaluation. It omits attachments, actual aircraft
availability, performance limits, permits, NOTAMs, weather, duty limits, and time-zone
conversion. Broad, independent synthetic authoring and double-reviewed annotations are
needed before drawing any conclusions about language-model generalization. Keep an
additional unseen test set when developing against the published challenge suite.

Contributions must be wholly synthetic or accompanied by verifiable public licensing.
The bundled loader currently accepts declared synthetic CC0 fixtures only; adding a
public licensed dataset requires a reviewed ingestion path and its own provenance card.
