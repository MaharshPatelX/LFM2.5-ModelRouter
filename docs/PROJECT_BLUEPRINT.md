# LFM2.5-ModelRouter Project Blueprint

**Status:** Governing implementation plan
**Project name:** `LFM2.5-ModelRouter` (selected)
**Primary checkpoint name:** `LFM2.5-ModelRouter-350M`
**Proposed paper title:** **LFM2.5-ModelRouter: Sparse Cold-Start Routing for Evolving LLM Portfolios**
**Primary encoder:** `LiquidAI/LFM2.5-Encoder-350M`
**Detailed research reference:** [`RESEARCH_HANDOFF.md`](RESEARCH_HANDOFF.md)
**Current progress:** [`PROJECT_TRACKER.md`](PROJECT_TRACKER.md)

This document is the practical build order for the project. Each numbered part is a real system component or a required research stage. We will follow the parts in order and will not treat a later part as complete until its entry conditions are satisfied.

The longer research handoff explains the literature and scientific motivation. This blueprint defines what we will build, what each part produces, and how we decide that it works.

---

## 1. Project in Simple Language

LFM2.5-ModelRouter is a small system that chooses which AI model should answer a request.

For every prompt, it will:

1. Understand what kind of task the user is asking for.
2. Look at the capabilities of every currently available model.
3. Predict each model's likely quality, token usage, latency, and failure risk.
4. Read the current model prices and availability.
5. Apply the user's quality, cost, and latency preferences.
6. Select one valid model.
7. Observe the selected model's result.
8. Adapt when model quality, traffic, prices, or availability change.

The central research question is:

> Can a 350M Liquid encoder learn when to use a completely unseen model after seeing only a small behavioral probe set, while continuing to route well as prices and model quality change?

---

## 2. End-to-End System Flow

```text
Incoming prompt
    |
    v
Query encoder
    |
    +-----------------------+
    |                       |
    v                       v
Candidate model profiles    Live registry
    |                       |-- prices
    |                       |-- availability
    |                       |-- constraints
    +-----------+-----------+
                |
                v
Outcome predictor
    |-- predicted success/quality
    |-- predicted output tokens
    |-- predicted latency
    |-- predicted failure risk
    |-- uncertainty
                |
                v
Runtime optimizer
    |-- intelligence mode
    |-- balanced mode
    |-- cost mode
    |-- hard constraints
                |
                v
Selected model
                |
                v
Observed result and cost
                |
                v
Online adapter and drift tracking
```

---

## 3. Three Boundaries We Must Preserve

### 3.1 Offline capability predictor

Learns relatively stable facts from historical data:

- Which kinds of prompts a model can solve.
- Expected answer quality or success probability.
- Expected output length.
- Expected latency under a known serving setting.
- Failure probability.
- Prediction uncertainty.

### 3.2 Runtime optimizer

Uses information that can change immediately:

- Current input and output prices.
- Current availability and rate limits.
- User preference weights.
- Maximum cost or latency.
- Context length, modality, privacy, and tool requirements.

A price-only change must not require training or gradient updates.

### 3.3 Online adapter

Learns from deployment-style feedback:

- Only the selected model's outcome is revealed.
- Recent evidence can outweigh old evidence.
- New models receive bounded exploration.
- Quality regressions are detected.
- Average spending remains close to the configured budget.

These three components must remain separate in code, configuration, tests, and evaluation.

---

## 4. Non-Negotiable Project Rules

1. Start with clean data and reproducible baselines before training LFM.
2. Keep prices in an external, versioned runtime table.
3. Preserve raw input tokens, output tokens, latency, and raw quality metrics.
4. Score candidate models independently; do not make the main model a fixed `num_models` classifier.
5. Do not expose hidden counterfactual outcomes to the online policy.
6. Keep probe questions disjoint from final routing test questions.
7. Test completely held-out models and held-out model families.
8. Compare against strong simple and learned baselines.
9. Record seeds, configurations, dataset revisions, model revisions, prices, and licenses.
10. Report negative results and limitations.
11. Do not begin PPO, GRPO, multi-model aggregation, or a web dashboard for the research MVP.
12. Do not claim access to private production traffic or Cursor's internal router.

---

## 5. Key Terms

- **Query:** The user's prompt or task.
- **Candidate model:** A model that the router is allowed to select.
- **Outcome:** What happened when one candidate answered one query.
- **Probe:** A small test question used to learn about a new model.
- **Behavioral profile:** A fingerprint built from a model's probe results.
- **Offline training:** Learning from stored outcomes before deployment.
- **Full feedback:** Stored results are available for all candidates on a query.
- **Bandit feedback:** Only the selected candidate's result is revealed.
- **Churn:** Prices, models, availability, quality, or traffic changing over time.
- **Oracle:** An impossible production policy that sees all outcomes and chooses the best one. It is used only as an evaluation ceiling.
- **Regret:** The difference between the router's result and the oracle's result.
- **Pareto frontier:** The set of choices where quality cannot improve without increasing cost or latency.

---

## 6. Ordered System Parts

## Part 0 — Project Contract and Scope

### Purpose

Agree on the system boundaries and prevent the project from expanding before the core experiment works.

### Build

- Maintain this blueprint.
- Keep the detailed research handoff as supporting context.
- Select a final public project name before public release.
- Define version one as one decision:

```text
action = (model, optional_reasoning_mode, optional_output_budget)
```

### Outputs

- `docs/PROJECT_BLUEPRINT.md`
- Research question and novelty statement.
- MVP definition of done.

### Completion gate

- The blueprint exists and is accepted as the implementation order.
- No code is required for this part.

### Status

**Complete.**

---

## Part 1 — Reproducible Repository Foundation

### Purpose

Make every later result repeatable and testable.

### Build

- Python package using a `src/` layout.
- `pyproject.toml` with pinned compatible dependency ranges.
- Ruff formatting and linting.
- pytest test suite.
- Static type checking.
- Deterministic random seed helpers.
- YAML or similarly simple experiment configurations.
- Local JSON/Parquet experiment logging.
- CI for formatting, types, and small tests.
- Git ignore rules for raw data, caches, checkpoints, and secrets.

### Outputs

- Installable package.
- Passing smoke test.
- Minimal README that states the research question without claiming results.
- Initial directory structure.

### Completion gate

- A clean environment can install the package.
- Formatting, type checks, and unit tests run successfully.
- No dataset or model download is required for the smoke test.

### Status

**Next.**

---

## Part 2 — Dataset Source Audit and Ingestion

### Purpose

Understand the real xRouteBench files before designing around them.

### Build

- Pin the xRouteBench dataset revision used by experiments.
- Record configurations, splits, files, row counts, columns, dtypes, and missingness.
- Confirm download requirements.
- Confirm license and redistribution rules.
- Download a small sample first.
- Create an adapter that reads the source without silently changing values.
- Record exact source URLs and verification dates.

### Outputs

- `reports/xroutebench_audit.md`
- Machine-readable schema snapshot.
- Dataset manifest with revision and checksums where practical.
- Small local sample for tests.
- xRouteBench ingestion adapter.

### Completion gate

- The adapter loads the sample deterministically.
- Reported schema matches the pinned source files.
- License and redistribution conditions are documented.
- No schema assumption exists only because it appeared in the research handoff.

---

## Part 3 — Canonical Data Layer

### Purpose

Give every source dataset the same internal format.

### Build

Six canonical tables:

1. **Query table** — prompt, task, source, ground truth, metric and modality.
2. **Model registry** — stable ID, provider, family, version and capabilities.
3. **Outcome table** — query/model execution, score, tokens, latency and failures.
4. **Price history** — versioned input, cached-input and output prices.
5. **Probe profile table** — anchor query and observed model behavior.
6. **Online route log** — candidate set, selected action, probability, predictions and feedback.

Additional requirements:

- Store canonical data as Parquet.
- Support JSONL debug exports.
- Validate required fields, ranges, IDs and relationships.
- Preserve raw source fields when normalization would lose information.

### Outputs

- Canonical schema models.
- Parquet builders.
- Validation tests.
- Price recomputation function.

### Completion gate

- Invalid rows fail with understandable errors.
- Model and query references are consistent.
- Recomputing cost from tokens and a price snapshot is tested.
- Changing a price snapshot changes computed cost without changing stored outcomes.

---

## Part 4 — Deduplication and Leakage-Safe Splits

### Purpose

Ensure test performance measures generalization rather than memorization.

### Build

- Exact prompt hashing.
- Normalized-text hashing.
- Near-duplicate checks where practical.
- Alias and model-family mapping.
- Probe/test separation checks.
- Reproducible split manifests for:
  - Prompt-IID split.
  - Task-held-out split.
  - Model-held-out split.
  - Family-held-out split.
  - Temporal split.
  - Joint new-model/new-task split.

### Outputs

- Versioned split manifests.
- Deduplication report.
- Leakage tests.

### Completion gate

- The same seed recreates the same splits.
- No query ID, exact prompt, or known duplicate crosses a prohibited boundary.
- Held-out models do not leak through aliases unless explicitly allowed by an experiment.
- Probe questions do not appear in final test traffic.

---

## Part 5 — Baseline Suite

### Purpose

Establish what can be achieved without the proposed LFM/profile system.

### Build

Simple baselines:

- Random valid model.
- Cheapest model.
- Largest or most expensive model.
- Best single model selected on training/validation data.
- Per-domain best model.
- Oracle best-quality model.
- Oracle cheapest successful model.

Initial learned baselines:

- Logistic regression on frozen sentence embeddings.
- Small MLP on frozen sentence embeddings.
- Fixed learned model-ID predictor.
- LightGBM or XGBoost where appropriate.

### Outputs

- Reproducible baseline command.
- Baseline result table.
- First quality-versus-cost plot.
- Oracle gap report.

### Completion gate

- Every baseline runs end to end on the same split.
- All policies use the same candidate pool and cost calculation.
- Learned methods are compared to best-single and oracle results.

---

## Part 6 — LFM Query Encoder

### Purpose

Create a compact semantic representation of each incoming prompt.

### Build

- Pin the exact LFM model repository revision.
- Review its license and custom loading code.
- Implement tokenization, batching and pooling.
- Support CPU and GPU inference.
- Cache query embeddings with revision-aware keys.
- Begin with a frozen encoder.
- Later compare last-block and full fine-tuning as ablations.

### Outputs

- Query encoder module.
- Embedding cache format.
- CPU/GPU smoke tests.
- Router-overhead benchmark.

### Completion gate

- Repeated encoding is deterministic in evaluation mode.
- Cache invalidates when the model revision or preprocessing changes.
- Frozen embeddings can train a small baseline head.
- License implications for releasing weights are documented.

---

## Part 7 — Candidate Model Profile System

### Purpose

Represent known and completely new models without relying only on permanent model IDs.

### Build

Static metadata features:

- Provider and family.
- Architecture and parameter information when known.
- Context length.
- Modalities and tool support.
- Reasoning modes.
- Quantization and serving backend.
- Release/version date.

Behavioral features:

- Per-probe quality or success.
- Output tokens.
- Latency.
- Failure and format reliability.
- Missing-value mask.

Profile variants:

- Learned model ID.
- Metadata only.
- Domain aggregates.
- Fixed-order query-level probe vector.
- Structured metadata plus probe behavior.
- Query-conditioned set/attention profile as the research version.

### Outputs

- Public versioned anchor-set manifest.
- Probe selection code.
- Model-profile encoder.
- Profiles for 0, 8, 16, 32, 64, 128, 256 and optionally 500 probes.

### Completion gate

- A new model can receive a profile without changing output-layer dimensions.
- Missing probes are handled explicitly.
- Probe manifests are reproducible and disjoint from tests.

---

## Part 8 — Multi-Outcome Predictor

### Purpose

Estimate what will happen before a candidate model is called.

### Build

Combine the query embedding and model profile to predict:

- Success probability.
- Continuous normalized quality.
- Log output tokens.
- Log latency or latency quantiles.
- Provider/format failure probability.
- Uncertainty.

Training objectives may include:

- Binary cross-entropy for success.
- Huber loss for quality, tokens and latency.
- Pairwise ranking loss under sampled user preferences.
- Optional contrastive query/model loss.
- Post-training calibration.

### Outputs

- Shared interaction model.
- Separate prediction heads.
- Saved configurations and checkpoints.
- Calibration artifacts.

### Completion gate

- Prediction metrics are reported on untouched test data.
- Missing targets are correctly masked.
- Calibration is measured, not assumed.
- Candidate models are scored independently.

---

## Part 9 — Runtime Registry, Constraints and Optimizer

### Purpose

Turn outcome predictions into an actual routing decision using live state.

### Build

- Dynamic model registry with add/remove operations.
- Versioned live price lookup.
- Availability and rate-limit state.
- Hard filters for context, modality, privacy, tools, price and latency.
- Expected dollar-cost calculation from predicted tokens.
- Preference-conditioned utility.
- Named presets:
  - Intelligence.
  - Balanced.
  - Cost with a minimum success threshold.
- Selection log containing predictions and decision reasons.

### Outputs

- Runtime optimizer API.
- Constraint engine.
- Price and availability update API.
- Tests for all named modes.

### Completion gate

- An unavailable or incompatible model is never selected.
- A pure price update can change the selected model immediately.
- No model weight or checkpoint changes during a price-only test.
- Cost mode respects its configured success threshold when possible.

---

## Part 10 — Static Offline Evaluation

### Purpose

Measure routing quality before introducing online adaptation.

### Build

Prediction metrics:

- AUROC and AUPRC.
- Brier score and expected calibration error.
- Quality MAE and rank correlation.
- Token and latency error.
- Model recall, especially when only one model succeeds.

Routing metrics:

- Average quality and success rate.
- Cost per request.
- Average and p95 latency.
- Router inference latency.
- Cost at matched quality.
- Quality at matched cost.
- Pareto distance and hypervolume.

### Outputs

- Static evaluation report.
- Raw result files.
- Reproducible figure scripts.
- Pareto table and plots.

### Completion gate

- Proposed methods are compared on identical queries and price snapshots.
- Strong simple baselines are included.
- Confidence intervals are reported for headline metrics.

---

## Part 11 — Unseen-Model Cold-Start Experiments

### Purpose

Test the main scientific claim: useful routing for a model absent from training.

### Build

- Hold out several complete models.
- Hold out at least one complete family when data allows.
- Onboard each model using increasing probe counts.
- Compare random, stratified, diverse and learned probe selection.
- Perform limited online exploration after onboarding.

Main comparisons:

- Fixed ID only.
- Metadata only.
- Behavioral profile only.
- Metadata plus behavioral profile.
- Independent-arm bandit.
- Shared LFM prior plus online residual.

### Outputs

- Regret-versus-probe-count graph.
- Per-held-out-model results.
- Held-out-family report.
- New-model adoption curves.

### Completion gate

- Results exist for multiple probe counts and random seeds.
- No held-out-model outcomes outside the allowed probes leak into training.
- The proposed method is compared to a strong cold-start baseline.

---

## Part 12 — Non-Stationary Replay Simulator

### Purpose

Create a controlled environment where portfolio changes happen over time.

### Build

Event types:

- Price change.
- Quality regression or improvement.
- Latency shift.
- Provider failure spike.
- Model addition.
- Model removal.
- Traffic-distribution shift.
- User-preference shift.
- Budget change.

Required stream:

1. Stable period.
2. Major price cut.
3. Model-quality regression.
4. Held-out model arrival with a limited probe profile.
5. Existing model removal.

Feedback rule:

- The policy sees only the selected action's outcome.
- Hidden outcomes are available only to the simulator's oracle and evaluator.

### Outputs

- Event-driven environment.
- Deterministic replay streams.
- Dynamic oracle.
- Regret, budget and recovery metrics.

### Completion gate

- Replaying the same seed produces the same event stream.
- Tests prove hidden outcomes are not passed to the policy.
- Price, quality, addition and removal events all change environment state correctly.

---

## Part 13 — Online Adapter and Budget Pacing

### Purpose

Adapt safely using only deployment-style feedback.

### Build

- Epsilon-greedy baseline.
- Standard LinUCB.
- Discounted LinUCB.
- Optional Thompson or NeuralLinear baseline.
- Shared LFM prior plus per-model residual update.
- Geometric forgetting.
- Uncertainty-driven exploration.
- Bounded forced exploration for new models.
- Primal-dual average-budget controller.
- Action-probability logging.

### Outputs

- Online policy modules.
- Budget pacer.
- Drift and staleness tracking.
- Churn experiment results.

### Completion gate

- Only the selected action updates the policy.
- The policy reacts to quality drift.
- New models receive bounded, budget-aware exploration.
- Average-cost violations are measured and remain within the declared tolerance.
- Results are compared with a ParetoBandit-style baseline.

---

## Part 14 — External and Extended Benchmarks

### Purpose

Show that the system is not specialized only to xRouteBench.

### Build

Benchmark order:

1. **LLMRouterBench** for modern math, code, knowledge, tool-use, cost and latency evaluation.
2. **RouterArena** as an external black-box test after development choices are frozen.
3. **R2-Bench** when output-token budget becomes part of the action.
4. Optional older RouterBench/SPROUT runs for historical baseline reproduction.

### Outputs

- Dataset adapters as needed.
- Cross-dataset evaluation table.
- Task and family generalization report.
- Model-plus-token-budget extension results when implemented.

### Completion gate

- External test data is not used to tune the final method.
- Metrics and normalization differences are documented.
- Results are reported per domain rather than hidden in one unexplained score.

---

## Part 15 — Ablations, Statistics and Research Validation

### Purpose

Determine which components actually cause improvements.

### Build

Required ablations:

- No profile versus fixed ID.
- Metadata versus behavioral profiles.
- Domain-level versus query-level profiles.
- Different probe counts and selection methods.
- Frozen versus partial versus full LFM fine-tuning.
- No ranking loss.
- No preference conditioning.
- Historical price labels versus runtime prices.
- No uncertainty bonus.
- No forgetting.
- No offline prior.
- No forced exploration.

Statistical requirements:

- At least five seeds for lightweight experiments.
- Paired evaluation on identical replay streams.
- Bootstrap confidence intervals over queries or streams.
- Compute and API costs recorded.
- Model and price snapshot dates recorded.

### Outputs

- Ablation table.
- Confidence intervals.
- Negative-results section.
- Final evidence for or against every hypothesis.

### Completion gate

- Headline claims are supported by controlled comparisons.
- Variability across seeds is visible.
- Failed hypotheses are reported honestly.

---

## Part 16 — Research Release

### Purpose

Turn the experiments into a credible open-source research artifact.

### Build

- Final README.
- Dataset and license manifest.
- Public probe-set manifest.
- Reproducible configurations.
- Raw result artifacts.
- Figure-generation scripts.
- Static and churn evaluation reports.
- Model card.
- Research paper or preprint.
- Trained weights only if the relevant licenses allow distribution.
- Small demo only after the research pipeline is stable.

### Signature figures

1. Time series of model traffic, quality, cost and regret with event markers.
2. Routing regret versus number of new-model probes.

### Completion gate

- A clean environment can reproduce the main tables and figures.
- Claims match saved results.
- Limitations and licenses are visible.
- The README does not imply access to private production data.

---

## Part 17 — Later Extensions, Not MVP Requirements

Only consider these after Parts 1–16 are strong:

- Sequential escalation from a cheap model to a stronger one.
- A second-model verification action.
- Sticky task-level routing.
- Turn-level routing with cache-switch penalties.
- Delayed final reward for agent tasks.
- SWE-Bench, tau-squared Bench or terminal-task evaluation.
- Multi-round generative router.
- PPO or GRPO-style optimization.
- Answer aggregation across multiple models.

---

## 7. Training, Testing and Deployment in One View

### Offline training

```text
Stored full-feedback outcomes
    -> safe training split
    -> query and model representations
    -> quality/token/latency/failure predictor
    -> calibration
```

### Offline testing

```text
Untouched queries and/or held-out models
    -> router predictions
    -> runtime price optimizer
    -> compare chosen result with stored outcomes and oracle
```

### Online replay

```text
One query arrives
    -> router selects one action
    -> only selected outcome is revealed
    -> online adapter updates
    -> hidden outcomes calculate regret after the decision
```

### Real deployment later

```text
Live request
    -> route using current registry and prices
    -> selected model answers
    -> log consented quality/cost/latency feedback
    -> safe online update
```

---

## 8. Benchmark Roles

| Benchmark | Role in this project | Used for training? | Used for final testing? |
|---|---|---:|---:|
| xRouteBench training split | Primary development data | Yes | No |
| xRouteBench validation split | Configuration selection | No | No |
| xRouteBench untouched test splits | Main internal evaluation | No | Yes |
| xRouteBench held-out models/families | Cold-start evaluation | Only allowed probes | Yes |
| LLMRouterBench | Cross-dataset and current-model validation | Optional later | Yes |
| RouterArena | External black-box evaluation | No | Yes |
| R2-Bench | Model plus token-budget extension | Later | Yes |
| ParetoBandit-style replay | Churn and budget protocol | Online selected arms only | Yes |

---

## 9. Research Hypotheses

### H1 — Behavioral profiles help cold start

Models represented with 32–128 diverse probes will route better than models represented only by names or metadata.

### H2 — Shared semantic knowledge reduces exploration

The LFM prior will find a new model's useful task niche with fewer online calls than an independent-arm bandit.

### H3 — Runtime pricing removes needless retraining

A price-only change will update routing decisions immediately without modifying learned parameters.

### H4 — One preference-conditioned system gives a better frontier

One router supporting continuous preferences will provide smoother trade-offs than three unrelated classifiers.

### H5 — Token-budget actions improve reasoning efficiency

Jointly selecting a model and output budget will sometimes beat selecting a model alone.

### H6 — Final task reward may change the best model

For agent tasks, a more expensive call may be cheaper overall if it finishes the task in fewer turns.

---

## 10. MVP Definition of Done

The research MVP is complete only when:

- The xRouteBench pipeline is pinned, audited and reproducible.
- Canonical tables and leakage-safe splits are tested.
- At least five simple or learned baselines run end to end.
- The LFM predictor estimates quality and token usage.
- Live prices are injected at runtime.
- Intelligence, Balanced and Cost modes work without retraining.
- At least one completely held-out model experiment exists.
- New-model profiles are evaluated across multiple probe counts.
- Replay contains price change, quality regression, model addition and removal.
- The online adapter sees only selected-arm outcomes.
- Dynamic regret, budget compliance and recovery time are reported.
- A strong discounted-LinUCB/ParetoBandit-style baseline is included.
- External evaluation is reported.
- Tests, configs, seeds, raw results and figure scripts are present.
- Limitations and licenses are documented.

---

## 11. Naming Direction

`LFM-ChurnRouter` describes the mechanism, but "churn" is commonly associated with losing customers. This project will instead use a model-family naming style that immediately communicates the backbone, task and checkpoint size.

### Selected name

## LFM2.5-ModelRouter

Why it fits:

- **LFM2.5** identifies the Liquid model family.
- **ModelRouter** distinguishes this system from Liquid's existing prompt-lane router: this project predicts which downstream model should handle a query.
- The final size suffix identifies the actual backbone used by a checkpoint.
- The naming pattern can support multiple encoder sizes without renaming the project.

Recommended forms:

- Project/model family: `LFM2.5-ModelRouter`
- Primary checkpoint: `LFM2.5-ModelRouter-350M`
- Smaller checkpoint: `LFM2.5-ModelRouter-230M`
- Repository: `lfm-model-router`
- Python package: `lfm_model_router`
- Paper: **LFM2.5-ModelRouter: Sparse Cold-Start Routing for Evolving LLM Portfolios**
- Subtitle: **A 350M Liquid Encoder for Behavioral Model Onboarding and Adaptive Routing**

The current LFM2.5 bidirectional encoder family has 230M and 350M variants. Therefore, use `350M`, not an approximate `300M`, for the primary checkpoint. A future 1.2B or 2.6B generative router would be a different architecture and should be named separately, for example `LFM2.5-GenerativeRouter-1.2B`.

### Other technical candidates

1. `LFM2.5-Router-350M` — shortest, but too easily confused with prompt classification.
2. `LFM2.5-AdaptiveRouter-350M` — emphasizes online adaptation.
3. `LFM2.5-PortfolioRouter-350M` — accurately describes selection within a changing model portfolio.
4. `LFM2.5-ProbeRouter-350M` — emphasizes the sparse behavioral-probe contribution.
5. `LFM2.5-ModelRouter-350M` — clearest overall and the recommended checkpoint name.

Before public release, perform final GitHub, package-index, domain and trademark checks for the selected name.

---

## 12. Immediate Next Action

Begin **Part 1 — Reproducible Repository Foundation** only.

Do not download the full dataset or train the Liquid encoder during Part 1. The next review point is a clean repository skeleton with passing local quality checks.
