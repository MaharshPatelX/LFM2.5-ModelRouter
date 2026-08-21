# Part 3 — Canonical Data Layer

## Current status

Part 3 is complete. Its implementation and real-data validation were merged
into `main` by
[PR #7](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/pull/7), with both
Python 3.11 and 3.12 CI passing.

The builder reads the 41 pinned xRouteBench Parquet files from `data/raw/`,
normalizes them into six versioned tables, validates the complete result in
memory, and only then writes it beneath ignored `data/processed/` storage.

## What was built

| Canonical table | Purpose | Real rows | Disk size |
|---|---|---:|---:|
| `queries` | One stable row per prompt/query | 16,907 | 13.27 MB |
| `models` | Stable model IDs, aliases, providers and families | 33 | 0.02 MB |
| `outcomes` | One observed result for a query/model pair | 231,750 | 37.96 MB |
| `price_history` | Replaceable versioned token prices | 18 | 0.01 MB |
| `probe_profiles` | Future behavioral onboarding observations | 0 | <0.01 MB |
| `online_route_log` | Future live routing decisions and feedback | 0 | <0.01 MB |
| **Total** | Six typed Parquet tables | **248,708** | **51.26 MB** |

The row total counts rows across tables, not unique prompts. All sizes are
decimal megabytes and come from the current generated canonical manifest.

Of the 16,907 query rows, 15,339 have model outcomes and can enter Part 4.
The other 1,568 upstream validation rows are preserved with
`has_outcomes=false` instead of being silently discarded.

The two zero-row tables are intentional. xRouteBench does not define a
behavioral probe set or contain online routing traffic. They are still written
as correctly typed Parquet tables so later parts have a stable contract.

## Source-to-canonical rules

1. Every query gets a deterministic ID from its pinned dataset revision,
   configuration, split and source row index.
2. The original source record is preserved in `raw_source_json`; normalization
   does not destroy upstream fields.
3. Standard outcome files use `embedding_id` to reference the matching query.
   Every copied query field is checked against that query before conversion.
4. Each standard eligible query contributes outcomes for the 18 candidate
   models in the source registry.
5. Personalized comparisons contain two candidate answers and one judge
   choice. They become two query/model outcomes: the winner scores `1.0` and
   the other candidate scores `0.0`.
6. Exact model aliases are merged into 33 stable model records. Alias
   collisions across different stable IDs fail validation.
7. The 18 source price records are stored separately from outcomes. Cost is
   recomputed from immutable token counts plus a chosen price snapshot, so a
   price change never rewrites historical outcomes.

## Validation gates

The build stops with an understandable error when it finds:

- Missing or duplicate primary IDs.
- Invalid strings, booleans, timestamps, probabilities, token counts, prices,
  latency values or model capabilities.
- An outcome, price, probe or route that references an unknown query or model.
- An alias owned by two different model IDs.
- Token totals that disagree with input plus output tokens.
- A query whose `has_outcomes` flag disagrees with the outcome table.
- A probe whose referenced outcome belongs to another query/model pair.
- A selected route model that is absent from its candidate set.

The generated manifest records the row count, byte size and SHA-256 digest of
every Parquet table. JSONL files are capped debug views only; Parquet is the
canonical storage format.

## Run from a fresh clone

From the repository root:

```powershell
python -m pip install -e ".[dev,data]"
python scripts/download_xroutebench.py --all
python scripts/build_xroutebench_canonical.py --debug-limit 100
```

The default output is:

```text
data/processed/xroutebench/
  ea4b6e1b29d9a734f55f0a637baf326bad6aa681/
    canonical-v1/
      canonical_manifest.json
      queries.parquet
      models.parquet
      outcomes.parquet
      price_history.parquet
      probe_profiles.parquet
      online_route_log.parquet
      debug/*.jsonl
```

Everything remains inside the cloned project by default. An optional
`LFM_ROUTER_STORAGE_ROOT` value can move only the ignored data workspace for a
large run.

## Feed Part 4

```powershell
python scripts/build_leakage_safe_splits.py `
  --queries data\processed\xroutebench\ea4b6e1b29d9a734f55f0a637baf326bad6aa681\canonical-v1\queries.parquet `
  --models data\processed\xroutebench\ea4b6e1b29d9a734f55f0a637baf326bad6aa681\canonical-v1\models.parquet `
  --dataset-id ulab-ai/xRouteBench `
  --dataset-revision ea4b6e1b29d9a734f55f0a637baf326bad6aa681 `
  --canonical-schema-version canonical-v1 `
  --allow-unsupported-temporal
```

This produces five real leakage-safe split manifests plus an explicit
`temporal.unsupported.json` artifact. A real temporal split cannot be claimed
because xRouteBench has neither query timestamps nor model release dates. The
pipeline records that limitation and never invents dates.
