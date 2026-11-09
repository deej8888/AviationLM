# Frozen first v2 pilot inputs

Entirely synthetic, CC0-1.0. These are the exact 240 training / 24 validation / 1 unused
test records consumed by the first v2 pilot, with original file hashes in `manifest.json`.
The test record was not evaluated. This folder contains no operational/company data.

Generator 2.0 serialized evidence-ledger entries in process-dependent set order. The
emails and target labels were deterministic, but dataset bytes could differ between
Python hash seeds. Generator 2.1 sorts that ledger while preserving the sampled text,
targets, and scenario assignment. A cross-process regression test verifies stable bytes;
another verifies identical model inputs against this archive.

The original training manifest and benchmark results retain their actual hashes.
They have not been rewritten to pretend the pilot consumed canonicalized files.
Use these frozen inputs and `benchmarks/runs/v2-pilot-config.toml` to reproduce the
historical training recipe. New staged experiments use generator 2.1 in a fresh directory.
