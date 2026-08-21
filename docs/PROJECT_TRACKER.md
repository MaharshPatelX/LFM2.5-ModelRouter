# LFM2.5-ModelRouter Project Tracker

| Tracker summary | Current value |
|---|---|
| Last updated | 2026-08-21 |
| Current phase | Part 5 — Baseline Suite is next |
| Core progress | 5 of 17 parts complete (Parts 0–16) |
| Active model scope | `LFM2.5-ModelRouter-350M` only |
| Compute plan | Local RX 7900 XTX 24 GB VRAM with existing 16 GB RAM |
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
| 3 | Canonical Data Layer | ✅ Done | [PR #7](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/pull/7) merged; six real tables validated |
| 4 | Deduplication and Leakage-Safe Splits | ✅ Done | [PR #7](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/pull/7) merged; five real manifests plus an explicit unsupported-temporal artifact |
| 5 | Baseline Suite | ➡️ **Next** | Implement simple and learned baselines on the Part 4 manifests |
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

## Merged Data Foundation

- [x] Store real data in portable repository-local ignored directories.
- [x] Build and validate all six canonical Parquet tables.
- [x] Preserve stable IDs, raw fields, model aliases and price snapshots.
- [x] Generate five real leakage-safe split manifests.
- [x] Record temporal as unsupported instead of inventing source dates.
- [x] Recreate all 21 generated artifacts byte-for-byte.
- [x] Merge Parts 3 and 4 in PR #7 with Python 3.11 and 3.12 CI passing.

## Next Part Checklist — Part 5

- [ ] Define one shared evaluation contract and candidate pool for every baseline.
- [ ] Implement random, cheapest and largest/most-expensive policies.
- [ ] Implement best-single-model and per-domain-best policies using only training data.
- [ ] Implement best-quality and cheapest-successful oracle upper bounds.
- [ ] Add logistic-regression, small-MLP and fixed-model-ID learned baselines.
- [ ] Evaluate every method on the same Part 4 split manifest and price snapshot.
- [ ] Save a baseline result table, quality-cost plot and oracle-gap report.
- [ ] Add deterministic tests and a reproducible baseline command.

The [local compute plan](COMPUTE_PLAN.md) fixes the active scope at 350M and
uses the incoming 24 GB RX 7900 XTX with the existing 16 GB of host RAM. Part 5
remains CPU-first, so hardware arrival does not block the next implementation.

## How to Maintain This Tracker

1. Keep only one part marked **Next** or **In progress**.
2. Change **Next** to **In progress** when its implementation branch is created.
3. Mark a part **Done** only after its blueprint completion gate passes and its pull request is merged.
4. Add the merged pull request link in the evidence column.
5. Move **Next** to the following part in the same tracker update.
6. Update the date and progress count whenever a status changes.
7. For GPU-dependent parts, distinguish implementation-ready code from
   hardware-validated and experiment-complete work using the
   [staged engineering workflow](COMPUTE_PLAN.md#staged-engineering-workflow).
