# LFM2.5-ModelRouter Project Tracker

| Tracker summary | Current value |
|---|---|
| Last updated | 2026-08-21 |
| Current phase | Part 3 implementation is complete locally; review and merge are next |
| Core progress | 3 of 17 parts complete (Parts 0–16) |
| Optional work | Part 17 is deferred until the MVP is complete |

This file is the quick status board for the project. The
[project blueprint](PROJECT_BLUEPRINT.md) remains the source of truth for each
part's requirements and completion gate.

## Status Legend

| Symbol | Meaning |
|---|---|
| ✅ Done | Completion gate passed and the work is merged |
| 🚧 In progress | Work has started on a dedicated branch |
| ➡️ Next | The next part to begin |
| 🧩 Partial | Useful implementation exists, but the part cannot pass its completion gate yet |
| ⬜ Pending | Waiting for earlier parts |
| 💤 Deferred | Optional work outside the current MVP |

## Full Project Tracker

| Part | System part | Status | Evidence or next gate |
|---:|---|---|---|
| 0 | Project Contract and Scope | ✅ Done | Scope and research question are documented |
| 1 | Reproducible Repository Foundation | ✅ Done | [PR #1](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/pull/1) merged; CI passed |
| 2 | Dataset Source Audit and Ingestion | ✅ Done | [PR #6](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/pull/6) merged; pinned ingestion checks passed |
| 3 | Canonical Data Layer | 🚧 **In progress** | Six real tables built and validated; review and merge are pending |
| 4 | Deduplication and Leakage-Safe Splits | 🧩 **Partial** | Five real manifests generated; temporal is explicitly unsupported because source dates do not exist |
| 5 | Baseline Suite | ⬜ Pending | Complete Part 4 first |
| 6 | LFM Query Encoder | ⬜ Pending | Complete Part 5 first |
| 7 | Candidate Model Profile System | ⬜ Pending | Complete Part 6 first |
| 8 | Multi-Outcome Predictor | ⬜ Pending | Complete Part 7 first |
| 9 | Runtime Registry, Constraints and Optimizer | ⬜ Pending | Complete Part 8 first |
| 10 | Static Offline Evaluation | ⬜ Pending | Complete Part 9 first |
| 11 | Unseen-Model Cold-Start Experiments | ⬜ Pending | Complete Part 10 first |
| 12 | Non-Stationary Replay Simulator | ⬜ Pending | Complete Part 11 first |
| 13 | Online Adapter and Budget Pacing | ⬜ Pending | Complete Part 12 first |
| 14 | External and Extended Benchmarks | ⬜ Pending | Complete Part 13 first |
| 15 | Ablations, Statistics and Research Validation | ⬜ Pending | Complete Part 14 first |
| 16 | Research Release | ⬜ Pending | Complete Part 15 first |
| 17 | Later Extensions | 💤 Deferred | Consider only after the MVP release |

## Part 3 Local Completion Checklist

- [x] Define the six canonical table schemas.
- [x] Build the canonical query table from pinned xRouteBench rows.
- [x] Build the canonical model registry with stable IDs, families, and aliases.
- [x] Build the outcome table with query/model references and preserved source fields.
- [x] Build the price-history, probe-profile, and online-route-log schemas.
- [x] Add understandable validation for required fields, ranges, IDs, and relationships.
- [x] Add canonical Parquet writers and bounded JSONL debug exports.
- [x] Add tested price recomputation from token counts and price snapshots.
- [x] Save generated canonical data beneath ignored `data/processed/` storage.
- [x] Pass every Part 3 completion gate in the project blueprint locally.
- [ ] Review, open and merge the pull request before marking Part 3 done.

## Part 4 Prework Already Completed

- [x] Keep real data in portable, repository-local ignored directories.
- [x] Support an optional external-storage override without hard-coded paths.
- [x] Implement exact and normalized prompt hashing.
- [x] Implement deterministic near-duplicate checks and audit counts.
- [x] Implement source-ID and synthetic-lineage grouping.
- [x] Implement model alias and family validation.
- [x] Isolate complete probe clusters from final test traffic.
- [x] Implement all six split strategies.
- [x] Add deterministic manifests and a generated deduplication report.
- [x] Add unit tests for reproducibility and leakage boundaries.
- [x] Complete Part 3 canonical Parquet tables and JSONL debug exports locally.
- [x] Document temporal as unsupported because the pinned source has no dates.
- [x] Generate and validate real xRouteBench manifests in `data/processed/part4/`.
- [ ] Merge the Part 4 pull request and mark Part 4 as done here.

## How to Maintain This Tracker

1. Keep only one part marked **Next** or **In progress**.
2. Change **Next** to **In progress** when its implementation branch is created.
3. Mark a part **Done** only after its blueprint completion gate passes and its pull request is merged.
4. Add the merged pull request link in the evidence column.
5. Move **Next** to the following part in the same tracker update.
6. Update the date and progress count whenever a status changes.
