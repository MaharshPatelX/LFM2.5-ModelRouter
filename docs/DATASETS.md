# Datasets

## Current scope

xRouteBench is the only dataset in the first data milestone. Part 2 pins
revision `ea4b6e1b29d9a734f55f0a637baf326bad6aa681` and records its files,
configurations, splits, schemas, missingness, hashes, access, and license state.
See the [completed source audit](../reports/xroutebench_audit.md),
[manifest](../data/manifests/xroutebench.json), and
[schema snapshot](../data/manifests/xroutebench_schema.json).

No raw benchmark data is committed to this repository. The pinned source has
no declared dataset license or license file, so redistribution is not cleared.
Only an authored synthetic fixture is tracked for deterministic tests.

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

The first audit is complete. Future source revisions require a new immutable
pin, regenerated manifests, another integrity scan, and an explicit review of
schema and license changes; they must not silently replace the current pin.
