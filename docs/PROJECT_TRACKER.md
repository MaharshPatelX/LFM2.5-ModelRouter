# LFM2.5-ModelRouter Project Tracker

| Tracker summary | Current value |
|---|---|
| Last updated | 2026-08-21 |
| Current phase | Part 2 — Dataset Source Audit and Ingestion |
| Core progress | 2 of 17 parts complete (Parts 0–16) |
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
| ⬜ Pending | Waiting for earlier parts |
| 💤 Deferred | Optional work outside the current MVP |

## Full Project Tracker

| Part | System part | Status | Evidence or next gate |
|---:|---|---|---|
| 0 | Project Contract and Scope | ✅ Done | Scope and research question are documented |
| 1 | Reproducible Repository Foundation | ✅ Done | [PR #1](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/pull/1) merged; CI passed |
| 2 | Dataset Source Audit and Ingestion | ➡️ **Next** | Produce the audit, manifest, schema snapshot, sample, adapter, and tests |
| 3 | Canonical Data Layer | ⬜ Pending | Complete Part 2 first |
| 4 | Deduplication and Leakage-Safe Splits | ⬜ Pending | Complete Part 3 first |
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

## Next Part Checklist — Part 2

- [ ] Pin the exact xRouteBench dataset revision.
- [ ] Record source URLs, verification date, configurations, splits, files, row counts, columns, dtypes, and missingness.
- [ ] Confirm download requirements, license terms, and redistribution rules.
- [ ] Download and inspect a small sample before handling the full dataset.
- [ ] Implement an ingestion adapter that preserves source values.
- [ ] Save a machine-readable schema snapshot and dataset manifest.
- [ ] Add a small legally redistributable fixture and deterministic loading tests.
- [ ] Write `reports/xroutebench_audit.md`.
- [ ] Verify every Part 2 completion gate in the blueprint.
- [ ] Merge the Part 2 pull request and mark Part 2 as done here.

## How to Maintain This Tracker

1. Keep only one part marked **Next** or **In progress**.
2. Change **Next** to **In progress** when its implementation branch is created.
3. Mark a part **Done** only after its blueprint completion gate passes and its pull request is merged.
4. Add the merged pull request link in the evidence column.
5. Move **Next** to the following part in the same tracker update.
6. Update the date and progress count whenever a status changes.
