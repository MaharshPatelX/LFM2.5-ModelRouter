# Reproducibility

## Environment

- Supported foundation environment: Python 3.11 and 3.12.
- Package and development requirements live in `pyproject.toml`.
- Heavy ML dependencies will be added only after model and platform compatibility checks.
- CI runs formatting, linting, static types, tests, and package builds.

## Configuration

Repository defaults live in `configs/base.toml`. Every experiment must save the fully resolved configuration used for the run.

Real data, caches, and generated dataset artifacts use the repository's ignored
`data/raw/`, `data/interim/`, `data/processed/`, and `data/cache/` directories
by default. `LFM_ROUTER_STORAGE_ROOT` is an optional absolute external-storage
override, not a required machine-specific setting.

## Randomness

All split construction and experiments must accept an explicit seed. The default project seed is `3407`; multi-seed results must list every seed rather than reporting only the best run.

## Data provenance

- Pin dataset revisions.
- Preserve raw source metrics and token counts.
- Save source and schema manifests.
- Keep probe, training, validation, and test boundaries explicit.
- Never overwrite historical model outcomes or price snapshots silently.

The Part 3 canonical manifest records each table's row count, byte size and
SHA-256 digest. Part 4 manifests omit wall-clock generation time and include
the source and deduplication digests, so identical canonical inputs,
configuration and seed produce identical bytes.

## Model provenance

Record:

- Full model repository ID.
- Immutable revision or commit hash.
- Loading code revision.
- Tokenizer revision.
- `trust_remote_code` requirement.
- License and redistribution implications.
- Precision, device, context length, and pooling configuration.

## Experiment artifacts

Every reported run should retain:

- Resolved configuration.
- Code commit SHA.
- Dataset and model revisions.
- Price snapshot ID and verification date.
- Seed.
- Raw aggregate metrics.
- Compute and API cost when applicable.
- Figure-generation input files.

Generated artifacts belong outside Git unless they are compact, safe to redistribute, and necessary to reproduce a published result.
