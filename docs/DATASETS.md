# Datasets

## Current scope

xRouteBench is the only dataset planned for the first data milestone. Its current repository revision, files, configurations, splits, schema, missingness, license, and redistribution rules must be audited before full download or adapter implementation.

No raw benchmark data is committed to this repository.

## Planned benchmark roles

| Source | Planned role |
|---|---|
| xRouteBench | Primary development data, internal testing, and held-out-model experiments |
| LLMRouterBench | Later cross-dataset validation on modern math, code, tool use, cost, and latency |
| RouterArena | External black-box evaluation after model choices are frozen |
| R2-Bench | Later joint model and output-budget experiments |
| ParetoBandit protocol | Non-stationary budget and adaptation comparison |

## Required source manifest fields

Every ingested source must record:

- Dataset identifier and immutable revision.
- Verification date and source URLs.
- Configurations, splits, row counts, columns, and dtypes.
- File hashes where practical.
- License and redistribution notes.
- Download method and authentication requirements.
- Known missingness, aliases, duplicates, and evaluation caveats.

The first completed audit will be written to `reports/xroutebench_audit.md` with a machine-readable schema snapshot under `data/manifests/`.
