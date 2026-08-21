# xRouteBench Source Audit

| Audit field | Value |
|---|---|
| Dataset | `ulab-ai/xRouteBench` |
| Pinned revision | `ea4b6e1b29d9a734f55f0a637baf326bad6aa681` |
| Revision timestamp | 2026-08-15 22:23:28 UTC |
| Verified | 2026-08-21 |
| Project part | 2 — Dataset Source Audit and Ingestion |

## Result

xRouteBench is publicly downloadable without authentication at the pinned
revision. It contains 17 Hugging Face configs, 41 Parquet split files, and
245,903 physical rows across all configs. The files total **47,382,959 bytes**
(47.38 decimal MB or 45.19 MiB) and expand to an estimated 283,762,117 bytes in
memory.

The row total is not a unique-prompt count. It sums routing outcomes, raw-query
tables, and the model registry; many queries therefore appear in more than one
config and routing queries repeat across candidate models.

The source is usable for reproducible local research, but **redistribution is
not cleared**. The pinned dataset card has no `license` field, the Hub API has
no license tag, and the repository tree has no `LICENSE` file. Public access is
not itself a license grant. This project therefore commits no upstream rows and
uses an authored synthetic fixture for tests.

## Pinned Sources

- [Dataset page](https://huggingface.co/datasets/ulab-ai/xRouteBench)
- [Pinned repository tree](https://huggingface.co/datasets/ulab-ai/xRouteBench/tree/ea4b6e1b29d9a734f55f0a637baf326bad6aa681)
- [Pinned dataset card](https://huggingface.co/datasets/ulab-ai/xRouteBench/blob/ea4b6e1b29d9a734f55f0a637baf326bad6aa681/README.md)
- [Pinned revision API](https://huggingface.co/api/datasets/ulab-ai/xRouteBench/revision/ea4b6e1b29d9a734f55f0a637baf326bad6aa681)
- [Dataset size API](https://datasets-server.huggingface.co/size?dataset=ulab-ai%2FxRouteBench)
- [Official LLMRouter implementation](https://github.com/ulab-uiuc/LLMRouter)
- [LLMRouter paper](https://arxiv.org/abs/2608.06867)

The tracked [manifest](../data/manifests/xroutebench.json) records the exact
source paths, sizes, row counts, Git blob IDs, Xet hashes, and LFS SHA-256
hashes. The [schema snapshot](../data/manifests/xroutebench_schema.json) records
every observed field, dtype, split, and non-zero null count.

## Inventory

| Config | Kind | Splits (rows) | Columns | Size |
|---|---|---|---:|---:|
| `llm_candidates` | models | train 18 | 7 | 0.01 MB |
| `llmrouter_generic` | routing | train 80,802; test 67,122 | 14 | 21.40 MB |
| `llmrouter_generic_queries` | queries | train 4,489; valid 523; test 3,729 | 6 | 2.73 MB |
| `memory_locomo` | routing | train 15,930; test 5,652 | 16 | 0.68 MB |
| `memory_locomo_queries` | queries | train 885; valid 341; test 314 | 8 | 0.34 MB |
| `memory_longmemeval` | routing | train 4,986; test 1,818 | 16 | 1.51 MB |
| `memory_longmemeval_queries` | queries | train 277; valid 92; test 101 | 8 | 1.49 MB |
| `multimodal_geometry3k` | routing | train 8,640; test 1,098 | 14 | 3.82 MB |
| `multimodal_geometry3k_queries` | queries | train 480; valid 60; test 61 | 6 | 0.08 MB |
| `multimodal_mathvista` | routing | train 14,400; test 1,800 | 14 | 4.67 MB |
| `multimodal_mathvista_queries` | queries | train 800; valid 100; test 100 | 6 | 0.22 MB |
| `personalized` | pairwise | train 2,464; test 308 | 12 | 4.86 MB |
| `personalized_queries` | queries | train 2,464; valid 308; test 308 | 6 | 0.35 MB |
| `timeseries` | routing | train 17,568; test 2,286 | 14 | 3.80 MB |
| `timeseries_queries` | queries | train 976; valid 120; test 127 | 6 | 1.25 MB |
| `video` | routing | train 3,618; test 486 | 14 | 0.14 MB |
| `video_queries` | queries | train 201; valid 24; test 27 | 6 | 0.04 MB |

Totals by role are 228,978 routing/pairwise rows, 16,907 raw-query rows, and 18
candidate-model rows.

## Schema Findings

xRouteBench is not one uniform table. The adapter must preserve these source
families before Part 3 defines a canonical internal representation:

| Family | Observed shape |
|---|---|
| Candidate registry | 7 fields for model name, size, input/output prices, service, API ID, and description |
| Generic routing | 14 fields: six query fields plus model, response, token, latency, score, and embedding fields |
| Generic/raw queries | 6 query fields |
| Memory routing | 16 fields, adding `category` and `conversation_id`; `category` differs in dtype between LoCoMo and LongMemEval |
| Memory/raw queries | 8 fields |
| Video | `choices` is `list[string]`, unlike the string representation in most other configs |
| Personalized routing | A distinct 12-field pairwise-preference table with `model_1`, `model_2`, `answer_1`, `answer_2`, `judge`, and persona fields |

The schemas are identical between splits of the same config. They are not
identical between configs, and the adapter intentionally performs no renaming,
casting, null filling, decoding, or canonicalization.

## Missingness

All 41 pinned Parquet files were scanned directly. Only non-zero null patterns
are listed below; every unlisted column has zero nulls in its split.

| Config family | Missing fields |
|---|---|
| `llmrouter_generic` | `choices`: 27,702 train / 19,422 test; `task_id`: 54,900 train / 46,800 test |
| `llmrouter_generic_queries` | `choices`: 1,539 train / 179 valid / 1,079 test; `task_id`: 3,050 train / 350 valid / 2,600 test |
| Both memory routing configs | `choices` and `task_id` are null in 100% of rows |
| Both memory query configs | `choices` and `task_id` are null in 100% of rows |
| Geometry3K routing and queries | `task_id` is null in 100% of rows |
| MathVista routing and queries | `task_id` is null in 100% of rows |
| Time-series routing and queries | `task_id` is null in 100% of rows |
| Candidate, personalized, personalized-query, video, and video-query configs | No null values |

These nulls are source facts, not errors to repair during ingestion.

## Integrity Verification

The audit followed this order:

1. Resolve and pin the immutable Hub commit.
2. Download the smallest file first: `llm_candidates/train.parquet` (8,450 bytes).
3. Verify its SHA-256 as
   `ba72146533ae68641e382759c90ff5bc53eb903956d4e748b7f3c0111907541f`.
4. Download all 41 pinned Parquet files into ignored `data/raw/` storage.
5. Verify every file against its upstream LFS SHA-256 and byte size.
6. Scan the files directly for schemas, row counts, and null counts.
7. Cross-check the results against the Hugging Face revision, tree, rows, and size APIs.

All 41 hashes matched, and every local row count matched the source size API.

## Source Card Discrepancy

The pinned dataset-card prose reports 4,487 generic training queries, while the
pinned `llmrouter_generic_queries/train.parquet` file and the Hub APIs contain
**4,489** rows. The machine-readable manifest uses 4,489 because source files,
hashes, and API counts take precedence over prose.

## Download and Adapter Usage

Install the optional Parquet dependency:

```bash
python -m pip install -e ".[data]"
```

Download and verify only the smallest source sample (the safe default):

```bash
python scripts/download_xroutebench.py
```

Download and verify all 41 files:

```bash
python scripts/download_xroutebench.py --all
```

Read a pinned split without source-field transformations:

```python
from pathlib import Path

from lfm_model_router.data.adapters.xroutebench import XRouteBenchAdapter

manifest = Path("data/manifests/xroutebench.json")
root = Path("data/raw/xroutebench/ea4b6e1b29d9a734f55f0a637baf326bad6aa681")
adapter = XRouteBenchAdapter.from_manifest(data_root=root, manifest_path=manifest)

for row in adapter.iter_split("llm_candidates", "train"):
    print(row["model_name"])
```

The adapter verifies byte size, SHA-256, column order, dtypes, and final row
count. It yields the original Python values, including `None` and list values.

## License and Redistribution Decision

- Access at verification time: public, ungated, no token required.
- Declared dataset license: none found.
- Dataset license file: none found.
- Redistribution decision: do not commit or republish upstream rows.
- Test-data decision: commit only the authored synthetic fixture.
- Release requirement: obtain explicit dataset terms or author clarification
  before redistributing source rows or packaging derived row-level data.

The Apache-2.0 license used by related code, if any, must not be assumed to
cover this separately hosted dataset.

## Part 2 Completion Gate

| Gate | Evidence |
|---|---|
| Adapter loads a sample deterministically | Synthetic fixture and repeat-load tests; Parquet round-trip test exercises null/list preservation |
| Reported schema matches pinned files | 41 direct Parquet scans plus Hub rows API cross-check |
| License and redistribution conditions documented | This report, manifest, fixture notice, and data policy |
| No handoff-only assumptions | Revision, files, counts, fields, dtypes, nulls, access, and hashes were re-verified from live upstream sources |

Part 2 contains no canonical-table design, deduplication, split redesign,
baseline training, encoder work, or benchmark claims. Those remain later parts.
