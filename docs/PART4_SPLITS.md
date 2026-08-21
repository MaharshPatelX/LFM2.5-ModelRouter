# Part 4 — Deduplication and Leakage-Safe Splits

## Current status

Part 4 is complete. Its reusable engine and real xRouteBench validation were
merged into `main` by
[PR #7](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/pull/7). It consumes
the Part 3 canonical tables and generates five leakage-safe xRouteBench
manifests, a common deduplication manifest and an audit report.

The pinned xRouteBench source schema does not contain query timestamps or model
release dates. The temporal strategy therefore requires trustworthy provenance
metadata from another trustworthy source. The current run writes
`temporal.unsupported.json` with the exact reason; it never invents dates.

## Storage rule

Canonical data and generated artifacts use ignored directories inside the
cloned project by default:

```text
data/raw/
data/interim/
data/processed/
data/cache/
```

This keeps the repository portable: it can be cloned or moved to another drive
and run without changing any path. These directories remain excluded from Git.
`LFM_ROUTER_STORAGE_ROOT` may optionally point to an absolute external location
for a larger run; it is not required.

## Duplicate boundary

Each query receives:

- A SHA-256 hash of the exact UTF-8 prompt.
- A SHA-256 hash after Unicode NFKC, case-folding, and whitespace normalization.
- A deterministic token-shingle signature for near-duplicate candidate search.

Queries are joined into one atomic cluster when they share exact text,
normalized text, a source query ID, augmentation lineage, or an accepted
near-duplicate match. If any cluster member is a probe, the complete cluster is
placed in the probe partition and excluded from final test traffic.

Near-duplicate acceptance uses exact Jaccard similarity over hashed token
3-grams after deterministic candidate blocking. The default threshold is 0.90.
Over-broad candidate buckets are skipped and counted in the report so coverage
is auditable.

## Split definitions

| Strategy | Query boundary | Model boundary |
|---|---|---|
| `prompt_iid` | Duplicate cluster | All models shared |
| `task_held_out` | Whole task plus duplicate cluster | All models shared |
| `model_held_out` | Duplicate cluster | Stable model ID plus aliases |
| `family_held_out` | Duplicate cluster | Whole model family across every provider |
| `temporal` | Observed time plus duplicate cluster | Model availability time |
| `joint_new_model_new_task` | Whole task plus duplicate cluster | Stable model ID plus aliases |

For held-out model strategies, evaluation rows use the matching query and model
partitions. This keeps the test prompts unseen while also testing an unseen
model. Probe queries remain a separate onboarding set.

## Part 3 exchange contract

Part 4 consumes the Parquet query table and model registry produced by Part 3.
It also accepts their bounded JSONL debug views for small development checks,
but Parquet is the production exchange and canonical storage format.

Required query fields:

```text
query_id, prompt, task, source
```

Optional query fields used for stronger boundaries:

```text
source_query_id, lineage_id, observed_at, is_probe
```

Required model fields:

```text
model_id, provider, family, version
```

Optional model fields:

```text
aliases, available_at
```

All timestamps must be timezone-aware ISO-8601 values.

## Build command

After building the Part 3 tables:

```powershell
python scripts/build_leakage_safe_splits.py `
  --queries data\processed\xroutebench\ea4b6e1b29d9a734f55f0a637baf326bad6aa681\canonical-v1\queries.parquet `
  --models data\processed\xroutebench\ea4b6e1b29d9a734f55f0a637baf326bad6aa681\canonical-v1\models.parquet `
  --dataset-id ulab-ai/xRouteBench `
  --dataset-revision ea4b6e1b29d9a734f55f0a637baf326bad6aa681 `
  --canonical-schema-version canonical-v1 `
  --allow-unsupported-temporal
```

Outputs are written beneath:

```text
data\processed\part4\manifests\splits\<dataset>\<revision>\<version>\
data\processed\part4\reports\
```

Every manifest records dataset and schema versions, algorithm version, seed,
ratios, source digest, deduplication digest, explicit memberships, model alias
and family information, held-out entities, and temporal cutoffs when available.
No wall-clock generation time is stored, so identical inputs produce identical
manifest bytes.

## Real xRouteBench result

The current canonical input contains 15,339 eligible queries. Deduplication
forms 14,688 atomic clusters, including 435 clusters with multiple queries.
Five real strategies pass their leakage checks. Temporal is the sole
unsupported strategy because all 15,339 eligible queries lack `observed_at`.

## Completion status

The reproducibility and leakage gates pass, and the implementation is merged.
The temporal limitation is a property of xRouteBench's missing source dates,
not unfinished split-engine work.
