# LFM2.5-ModelRouter

## Complete Research, Dataset, Training, Evaluation, and Implementation Handoff

**Status:** Research and project-design document
**Prepared:** August 20, 2026
**Intended use:** Load this entire file into a new Codex/Cursor session before building the repository.
**Primary model:** `LiquidAI/LFM2.5-Encoder-350M` or its prompt-router fine-tune
**Selected project name:** **LFM2.5-ModelRouter**

---

## 0. Instructions for the Next Coding Agent

Read this document completely before writing code.

Do not immediately build a large RL system. Begin with the reproducible offline benchmark and a modular data representation. The project must keep the following three components separate:

1. **Offline capability predictor:** Predicts model quality, output length, latency, and uncertainty from a query and a model profile.
2. **Runtime optimizer:** Uses current prices, user preference weights, availability, and hard constraints to select an action. A price update must not require retraining.
3. **Online adapter:** Learns from bandit feedback, handles quality drift, and safely explores newly introduced models.

The first engineering goal is a clean dataset pipeline and simulator—not an impressive UI and not GRPO.

Before implementation, inspect current versions, licenses, file layouts, and download instructions for all selected datasets. Never assume a dataset schema from this document without validating the actual files because dataset repositories can change.

---

## 1. User Goal and Motivation

The goal is to build a technically credible ML research project using Liquid AI's small encoder models. The project should be strong enough to:

- Publish as an open-source repository.
- Share results and visuals on X/Twitter.
- Demonstrate real ML research ability rather than only application engineering.
- Support an application for an ML Researcher or adjacent research-engineering role at Liquid AI or another model/systems lab.
- Investigate a problem that matters in production: selecting the best available model under changing quality, price, latency, and model availability.

The original idea was to train a small Liquid model to choose the most capable model for each task under three user modes:

- **Intelligence:** Maximize expected task quality.
- **Balanced:** Trade quality against cost and latency.
- **Cost:** Select the cheapest model that is likely to succeed.

The important follow-up concern was that model prices change and models are continuously added, removed, updated, quantized, or replaced. A fixed classifier trained on permanent model IDs becomes stale. Cursor can retrain from extensive private traffic, but an independent researcher does not have that dataset.

This document defines a public-data solution to that problem.

---

## 2. Executive Research Verdict

### 2.1 Do public datasets exist?

Yes. There is enough public full-feedback data to train and evaluate a serious router:

- **xRouteBench** is the recommended primary dataset.
- **LLMRouterBench** adds current flagship, coding, tool-use, and cost data.
- **RouterEval** and **EmbedLLM** are valuable for learning model capability profiles.
- **R2-Bench** is useful if the action includes reasoning strategy or output-token budget.
- **SPROUT**, **RouterBench**, and **Arena human preferences** provide additional baselines and training signals.

### 2.2 What does not exist publicly?

There is no single public dataset containing all of the following:

- Continually changing API prices.
- Every newly released model.
- Real user satisfaction following an answer.
- Correction versus task-completion signals.
- Provider failures and rate limits.
- Cache hits and cache misses caused by switching models.
- Delayed final success for multi-turn agent tasks.
- Real user-specific quality/cost/latency preferences.
- Counterfactual outcomes from every model on every production request.

Therefore, the project should combine:

1. Public full-feedback data for offline pretraining.
2. A controlled non-stationary replay simulator.
3. Sparse online bandit feedback.
4. Optional small-scale real deployment logs later.

### 2.3 Is the basic idea novel?

Not by itself. The literature already includes:

- Static quality/cost routers.
- Preference-conditioned routers.
- Model embeddings and profiles.
- New-model generalization.
- Reasoning-budget selection.
- Online bandit routing.
- Explicit adaptation to price changes, quality regression, and model arrival.

Most importantly, **ParetoBandit** already evaluates changing prices, quality degradation, runtime model addition/removal, budget pacing, and online adaptation.

The project must therefore make a narrower and stronger contribution.

### 2.4 Recommended contribution

> **Can a 350M semantic encoder cold-start an unseen model from only 16–128 behavioral probes and maintain a quality–cost–latency Pareto frontier under price and quality churn?**

The strongest feasible novelty combination is:

- Small Liquid bidirectional encoder.
- Query-conditioned structured model fingerprints.
- Sparse unseen-model onboarding.
- Runtime prices kept outside learned weights.
- Preference-conditioned multi-objective selection.
- Online non-stationary adaptation.
- Optional extension from response-level reward to final agent-task reward.

---

## 3. Proposed Project in One Paragraph

**LFM2.5-ModelRouter** is a small, open, non-stationary LLM-routing system. An LFM2.5 350M encoder represents the incoming query. A separate model-profile encoder represents each candidate using metadata and a small behavioral probe set. Lightweight prediction heads estimate success probability, expected output tokens, latency, and uncertainty for every query–model–reasoning configuration. A runtime optimizer combines those predictions with a live price table and user preference vector. A discounted contextual bandit updates predictions from observed outcomes, detects quality drift, and explores new models without retraining the entire router.

---

## 4. System Boundaries

### 4.1 Version-one scope

Version one should select exactly one action:

```text
action = (model, optional_reasoning_mode, optional_output_budget)
```

It should not initially:

- Call multiple models and aggregate their answers.
- Generate free-form tool-call trajectories.
- Use a large generative router.
- Attempt fully autonomous production deployment.
- Claim to reproduce Cursor's private router.

### 4.2 Later extensions

After the one-step router is validated:

- Sequential escalation: cheap model first, stronger model only if needed.
- Verification action: call a second model to check the first answer.
- Agent-turn routing using conversation/tool history.
- Sticky task-level routing: use one backend throughout a task.
- Turn-level switching with explicit cache/switch penalty.
- Multi-round RL using PPO/GRPO-style objectives.

---

## 5. Why Liquid's Encoder Is Relevant

### 5.1 Models

- [LFM2.5 Encoder 350M](https://huggingface.co/LiquidAI/LFM2.5-Encoder-350M)
- [LFM2.5 Encoder 350M Prompt Router](https://huggingface.co/LiquidAI/LFM2.5-Encoder-350M-Prompt-Router)

Liquid describes the prompt-router checkpoint as a full fine-tune of the 350M encoder with a zero-shot routing head that scores a prompt against user-defined routing lanes in one encoder pass.

### 5.2 Why it fits this project

- Small enough to experiment with repeatedly.
- Bidirectional encoder is appropriate for classification, retrieval, similarity, and structured prediction.
- A router must be fast enough that routing overhead is negligible compared with downstream inference.
- Semantic lane scoring suggests a natural starting point for query–model compatibility.
- A 350M encoder is more interesting for Liquid-aligned research than using a generic MiniLM only.

### 5.3 What the existing prompt router does not provide

It does not automatically know:

- Which model will solve a specific query.
- Expected token usage.
- Current API price.
- Current model latency or availability.
- Whether a model recently regressed.
- How to introduce a model that did not exist during fine-tuning.
- How to optimize a changing multi-objective preference.

This project must add these capabilities.

### 5.4 License and implementation warning

The model card lists the Liquid model license rather than a generic Apache/MIT license and loads custom code with `trust_remote_code=True`. Confirm redistribution, fine-tuning, and weight-release rights before publishing trained checkpoints. Code and dataset-derived artifacts can still be released according to their respective licenses even if trained-weight distribution requires extra care.

---

## 6. Public Dataset Inventory

### 6.1 xRouteBench — Recommended primary dataset

- Dataset: [ulab-ai/xRouteBench](https://huggingface.co/datasets/ulab-ai/xRouteBench)
- Paper: [LLMRouter / xRouteBench](https://arxiv.org/abs/2608.06867)
- Code: [ulab-uiuc/LLMRouter](https://github.com/ulab-uiuc/LLMRouter)

Reported characteristics:

- Approximately 245,903 query–model rows.
- Eighteen candidate models.
- Every query is run against every candidate in the applicable scenario.
- Includes actual response, task score/performance, input tokens, output tokens, and response time.
- Generic routing data includes standard benchmarks such as MMLU, GSM8K, MATH, MBPP, ARC, and others.
- Additional scenarios include long memory, long-context evaluation, time series, images, video, geometry, multimodal math, and personalization.
- Raw queries are provided, which matters because new models can be rerun later.

Why use it:

- It is currently the most useful unified starting point for quality, token, latency, and cost-aware routing.
- Full feedback allows training an oracle-style offline predictor before simulating partial feedback.
- Multiple scenarios enable task-OOD tests.

Limitations:

- Candidate pool is still finite.
- Price information is a historical snapshot.
- Benchmark correctness is not equivalent to production satisfaction.
- It does not automatically model provider outages, caching, or delayed agent outcomes.

### 6.2 LLMRouterBench — Current flagship and tool/coding coverage

- Dataset: [NPULH/LLMRouterBench](https://huggingface.co/datasets/NPULH/LLMRouterBench)
- Paper: [LLMRouterBench](https://arxiv.org/abs/2601.07206)
- Code: [ynulihao/LLMRouterBench](https://github.com/ynulihao/LLMRouterBench)

Reported characteristics:

- 23,945 prompts.
- 391,645 model-execution instances.
- Thirty-three models total.
- Twenty-one datasets.
- Approximately 1.8B tokens.
- Twenty lightweight models around 7B for performance-oriented routing.
- Thirteen flagship/proprietary models for quality–cost routing.
- Fields include prompt/query, prediction/response, ground truth, score, prompt tokens, completion tokens, and cost.
- Covers math, code, logic, knowledge, affect, instruction following, SWE-Bench, and tau-squared tool-use evaluation.
- Includes adapters for ten representative routing methods.

Important paper conclusions:

- Different models have complementary strengths.
- Many sophisticated routers perform similarly under unified evaluation.
- Several routers fail to beat a strong best-single-model baseline reliably.
- A large gap remains to the per-query oracle.
- Many errors come from failure to recall the only candidate model that answered correctly.
- Embedding backbone choice often matters less than expected.
- Adding more models has diminishing returns; model-pool curation matters.

Use it for:

- Current-model evaluation.
- Hard math/code/tool-use tasks.
- Model recall analysis.
- Quality–cost–latency evaluation.

Limitations:

- Price snapshot is not live.
- Candidate pools remain fixed inside collected data.
- Some dataset files may require custom loading because the Hugging Face viewer is not fully configured.

### 6.3 RouterEval — Massive capability matrix

- Dataset/code: [MilkThink-Lab/RouterEval](https://github.com/MilkThink-Lab/RouterEval)
- Paper: [RouterEval](https://aclanthology.org/2025.findings-emnlp.208/)

Reported characteristics:

- More than 8,500 models.
- More than 200 million performance records.
- Twelve popular evaluation suites.

Use it for:

- Learning a broad model capability space.
- Studying model-level scaling and pool selection.
- Creating candidate behavioral fingerprints.
- Pretraining model representations before adapting to response-level datasets.

Limitations:

- Primarily a benchmark-performance matrix.
- Does not provide the same realistic per-request token, response, latency, cache, and API cost fields as xRouteBench.
- Many model records can be highly correlated or derived from similar benchmark leaderboards.

### 6.4 EmbedLLM dataset

- Paper/code/data: [EmbedLLM](https://github.com/richardzhuang0412/EmbedLLM)
- Paper: [arXiv 2410.02223](https://arxiv.org/abs/2410.02223)

Reported construction:

- 112 open models.
- 36,054 questions.
- Sources: MMLU, TruthfulQA, SocialQA, PIQA, MedMCQA, MathQA, LogiQA, GSM8K, GPQA, and ASDiv.
- Every model–question pair receives a binary correctness label using `lm-evaluation-harness`.
- Questions are split 80/10/10.
- Questions initially use `all-mpnet-base-v2` embeddings of dimension 768.
- The resulting label matrix has shape 112 × 36,054.

Use it for:

- Learning compact model embeddings.
- Designing behavioral fingerprints.
- Evaluating model-held-out generalization.

Limitations:

- No output-token, latency, or cost target.
- Learned ID embeddings alone cannot represent a completely unseen model.

### 6.5 SPROUT

- Dataset: [CARROT-LLM-Routing/SPROUT](https://huggingface.co/datasets/CARROT-LLM-Routing/SPROUT)

Reported characteristics:

- 44,241 rows.
- Thirteen candidate models.
- Six task families including math, general reasoning, and RAG-oriented tasks.
- Used by CARROT and later causal/online-routing work.

Use it for:

- A manageable, downloadable multi-model benchmark.
- Reproducing causal/off-policy and cost-aware baselines.

### 6.6 RouterBench

- Dataset: [withmartian/routerbench](https://huggingface.co/datasets/withmartian/routerbench)
- Paper: [RouterBench](https://arxiv.org/abs/2403.12031)
- Code: [withmartian/routerbench](https://github.com/withmartian/routerbench)

Reported characteristics:

- More than 30,000 prompts.
- Eleven LLMs.
- Includes model responses, task scores, and estimated inference cost.
- Prompts include MBPP, GSM8K, WinoGrande, HellaSwag, MMLU, MT-Bench, and other tasks.
- Includes zero-shot and few-shot variants.

Use it for:

- Historical baseline reproduction.
- Bandit replay because complete outcomes exist before hiding unchosen arms.

Limitations:

- Model pool and prices are old.
- It should not be the only benchmark for a 2026 project.

### 6.7 Chatbot Arena human preferences

- Dataset: [arena-human-preference-55k](https://huggingface.co/datasets/lmarena-ai/arena-human-preference-55k)
- Associated paper: [Chatbot Arena](https://arxiv.org/abs/2403.04132)

Reported characteristics:

- 57,477 public rows.
- More than 70 model identities.
- Two responses to the same user conversation.
- Human outcome: model A wins, model B wins, tie, or both bad.

Use it for:

- Learning an offline human-preference prior.
- Pairwise Bradley–Terry or preference models.
- Warm-starting a bandit such as PILOT.

Limitations:

- Pairwise rather than full model-pool outcomes.
- Model choice in collected battles is not random, producing exposure/confounding concerns.
- No dependable task-success ground truth.
- Prices and token counts may need reconstruction or may not exist.

### 6.8 R2-Bench

- Paper: [R2-Router](https://arxiv.org/abs/2602.02823)

Reported characteristics:

- Fifteen open models from approximately 0.6B to 235B.
- Six benchmarks including MMLU-Pro, OpenHermes, MATH, GPQA, MuSR, and RAGBench.
- Each query–model pair is evaluated at multiple output-length budgets.

Use it for:

- Treating reasoning effort/token budget as part of the action.
- Learning quality-versus-length curves instead of one fixed model score.
- Testing whether a cheap model with additional reasoning budget beats an expensive model.

### 6.9 Router-R1 training collection

- Code and released resources: [Router-R1](https://github.com/ulab-uiuc/Router-R1)

Reported construction:

- Approximately 14,000 training questions: about 7K Natural Questions and 7K HotpotQA.
- Candidate models are sampled multiple times for each question.
- Exact-match success and output-dependent cost can be computed.
- Candidate pool includes Qwen, Llama, Mistral, Mixtral, and Gemma families.

Use it only when moving toward multi-round routing.

### 6.10 RouterArena

- Dataset: [RouteWorks/RouterArena](https://huggingface.co/datasets/RouteWorks/RouterArena)

Reported characteristics:

- 8,400 queries.
- Nine domains.
- Forty-four categories.
- Multiple difficulty levels.

Use it as an external evaluation set. It is less suitable as direct supervised training data because the benchmark treats routing systems as black boxes and does not expose full per-query, per-model outcomes for arbitrary router training.

---

## 7. Literature Map: What Each Paper Trained

This section covers the major papers directly relevant to this project through August 20, 2026. It is not a claim that every arXiv paper containing the word “router” is included. For a continuously updated bibliography, use:

- [Dynamic Model Routing and Cascading for Efficient LLM Inference: A Survey](https://arxiv.org/abs/2603.04445)
- [Awesome Routing LLMs](https://github.com/MilkThink-Lab/Awesome-Routing-LLMs)

### 7.1 Large Language Model Routing with Benchmark Datasets

- Paper: [arXiv 2309.15789](https://arxiv.org/abs/2309.15789)
- Idea: Learn model selection from benchmark outcomes.
- Data: Benchmark questions and per-model correctness.
- Training: Performance prediction/binary classification for candidate models.
- Strength: Establishes the basic supervised routing formulation.
- Limitation: Fixed model set; benchmark distribution can differ heavily from real prompts.

### 7.2 FrugalGPT

- Paper: [arXiv 2305.05176](https://arxiv.org/abs/2305.05176)
- Code: [stanford-futuredata/FrugalGPT](https://github.com/stanford-futuredata/FrugalGPT)
- Idea: Cascade from cheaper to more expensive APIs.
- Training: DistilBERT-like response-quality estimators use the query and a generated answer. Thresholds determine whether to accept or escalate while satisfying budget constraints.
- Strength: Classic cost-aware cascade baseline.
- Limitation: The cheap model must first generate an answer, so unsuccessful calls add cost and latency.

### 7.3 HybridLLM

- Paper: [arXiv 2404.14618](https://arxiv.org/abs/2404.14618)
- Code: [m365-core/hybrid_llm_routing](https://github.com/m365-core/hybrid_llm_routing)
- Data: MixInstruct assembled from Alpaca-GPT4, Dolly, GPT4All-LAION, and ShareGPT; approximately 20K queries total, with 10K used for training and 5K/5K validation/test in reported experiments.
- Label generation: Multiple responses per model; BARTScore acts as a quality signal.
- Router: DeBERTa-v3-large, approximately 300M parameters.
- Training: Five epochs on a single A100 80GB in the reported setup.
- Objective: Binary small-versus-large selection, including deterministic and probabilistic variants.
- Lesson: A model near Liquid's 350M scale is sufficient for useful prompt-based routing.
- Limitation: Usually only a fixed pair of candidate models and a synthetic automatic quality metric.

### 7.4 RouteLLM

- Paper: [arXiv 2406.18665](https://arxiv.org/abs/2406.18665)
- Code: [lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM)
- Primary data: Approximately 80K Chatbot Arena battles in the original study, filtered to roughly 65K usable comparisons.
- Augmentation: MMLU gold labels and Nectar-derived comparisons judged by GPT-4.
- Routers:
  - Similarity-weighted Bradley–Terry.
  - Matrix factorization.
  - BERT-base classifier.
  - Llama-3-8B causal classifier.
- Objective: Predict whether a designated strong model will beat a designated weak model.
- Important result: Arena-only routing transferred poorly to some benchmark distributions; small amounts of in-domain gold data materially improved results.
- Limitation: Fundamentally oriented around strong-versus-weak pairs and a relatively fixed ability ordering.

### 7.5 ZOOTER

- Paper: [NAACL 2024](https://aclanthology.org/2024.naacl-long.109/)
- Process:
  1. Run all candidate LLMs on each training query.
  2. Score candidate answers with off-the-shelf Qwen reward models.
  3. Normalize scores into a soft target distribution.
  4. Distill targets into an mDeBERTa-v3-base router using KL divergence.
- Adds tag-based label enhancement for domain/task signals.
- Strength: Supervised reward distillation can replace expensive RL for one-step routing.
- Limitation: Quality is bounded by the reward model and full candidate inference is expensive.

### 7.6 RouterDC

- Paper: [NeurIPS 2024 paper](https://proceedings.neurips.cc/paper_files/paper/2024/file/7a641b8ec86162fc875fb9f6456a542f-Paper-Conference.pdf)
- Code: [shuhao02/RouterDC](https://github.com/shuhao02/RouterDC)
- Data: MMLU, GSM8K, CMMLU, ARC-Challenge, and HumanEval for training; PreAlgebra, MBPP, and C-EVAL for OOD tests.
- Candidate models: Seven 7B/8B models from Mistral, Llama, MetaMath, Zephyr, Chinese-specialized, and Dolphin variants.
- Label generation: Multiple sampled outputs; top-performing models treated as positives and bottom models as negatives.
- Router: Approximately 86M-parameter mDeBERTa-v3-base plus learned 768-dimensional model embeddings.
- Objective: Dual contrastive learning across query–model compatibility and query–query structure.
- Reported training: Around 1,000 optimization steps, AdamW, learning rate around `5e-5`, batch size 64 on an A100 80GB.
- Limitation: A pure learned model-ID embedding does not naturally represent a brand-new model.

### 7.7 EmbedLLM

- Paper: [arXiv 2410.02223](https://arxiv.org/abs/2410.02223)
- Data: 112 models × 36,054 questions with binary correctness.
- Router representation:
  - Learned model embedding.
  - Projected `all-mpnet-base-v2` query embedding.
  - Element-wise interaction followed by a linear classifier.
- Objective: Binary cross-entropy reconstruction of the correctness matrix.
- Strength: Compact model representations and very fast inference.
- Limitation: Fixed learned IDs and no explicit cost/latency objective.

### 7.8 GraphRouter

- Paper: [arXiv 2410.03834](https://arxiv.org/abs/2410.03834)
- Code: [ulab-uiuc/GraphRouter](https://github.com/ulab-uiuc/GraphRouter)
- Data: Alpaca, GSM8K, SQuAD, and Multi-News; approximately 600 queries per task in the reported setup, executed on ten LLMs.
- Features: GPT-4o-generated task/model descriptions containing strengths, price, and context information; BERT embeddings.
- Structure: Heterogeneous graph with task, query, and model nodes plus performance/cost edges.
- Objective: GNN edge prediction of the best query–model pairing.
- New-model experiment: Withhold some models and supply a small number of query interactions for them without retraining the entire system.
- Lesson: Behavioral interaction profiles are more useful than a model name alone.
- Limitation: If price is embedded inside a textual model profile, price changes can contaminate the learned representation. This project should keep price external.

### 7.9 Routoo

- Paper: [OpenReview](https://openreview.net/forum?id=RQ9fQLEajC)
- Candidate selection: Builds a complementary candidate universe from a very large Open LLM Leaderboard pool.
- Training data: ARC, MCTest, OpenBookQA, RACE, TruthfulQA, plus synthetic/hard examples; reported total around 75K training queries after filtering and augmentation.
- Router: Mistral-7B query encoder, learned model embeddings, linear performance predictor, and a greedy cost-aware decoder.
- Training: Uses high-rank LoRA in reported experiments.
- Strength: Joint candidate-pool curation and routing.
- Limitation: Router is much larger than needed for this project and model embeddings remain tied to a known pool.

### 7.10 IRT-Router

- Paper: [ACL 2025](https://aclanthology.org/2025.acl-long.761/)
- Code: [Mercidaiha/IRT-Router](https://github.com/Mercidaiha/IRT-Router)
- Evaluated on 20 models and 12 datasets.
- Method: Multidimensional Item Response Theory treats LLMs as test takers with latent abilities and prompts as items with latent difficulty/discrimination.
- Adds semantic online query warm-up.
- Strength: Interpretable model abilities and query difficulty.
- Limitation: Capability representation can still depend on historical test outcomes and a relatively stable action pool.

### 7.11 ICL-Router

- Paper: [arXiv 2510.09719](https://arxiv.org/abs/2510.09719)
- Code: [lalalamdbf/ICL-Router](https://github.com/lalalamdbf/ICL-Router)
- Benchmarks: Five in-distribution and five OOD reasoning/code benchmarks in reported experiments.
- Models: Eight open models.
- Components:
  - Frozen Qwen3-Embedding-8B.
  - Two-layer projector.
  - Qwen2.5-7B router.
- Training:
  - Query-reconstruction pretraining.
  - Model-profile stage using about 500 representative challenging queries.
  - Joint projector/router training.
- New model: Run the same profiling queries and construct an in-context behavioral representation without full retraining.
- Lesson: Behavior-based cold start works, but 500 probes and large backbones are expensive.

### 7.12 ZeroRouter

- Paper: [arXiv 2601.06220](https://arxiv.org/abs/2601.06220)
- Code: [Codeffun3/ZeroRouter](https://github.com/Codeffun3/ZeroRouter)
- Model space: Approximately 200 models from Open LLM Leaderboard data.
- Representation: A multidimensional 2PL IRT latent space, reported dimension 20.
- Query predictor: DistilBERT-base predicts difficulty/discrimination.
- Runtime selection: Integer optimization combines predicted accuracy, cost, latency, and user weights.
- Evaluation: Includes models released after the profiling cutoff.
- Strength: Explicit unseen-model and multi-objective framing.
- Limitation: A new model still needs enough information to locate it in the ability space.

### 7.13 Scope — Models Under Scope

- Paper: [arXiv 2601.22323](https://arxiv.org/abs/2601.22323)
- Full name: Scalable and Controllable Outcome Performance Estimator.
- Method: Retrieve examples of how candidate models behaved on similar problems; use an RL-trained reasoning model to predict correctness and token length before selecting a model.
- Strength: Predicts explicit performance and cost rather than outputting a fixed model class; supports new models represented by behavior.
- Limitation: Generative reasoning router is considerably heavier than a 350M encoder and more complex to serve.

### 7.14 R2-Router

- Paper: [arXiv 2602.02823](https://arxiv.org/abs/2602.02823)
- Data: R2-Bench with multiple output-length budgets per query/model.
- Router: Qwen3-Embedding-0.6B plus a three-layer MLP quality predictor; LightGBM is also evaluated.
- Prediction: Quality as a curve over reasoning/output length rather than one fixed score.
- New model: A small number of anchor points can interpolate its curve; the paper reports useful results with roughly 6–8 curve anchors in some settings.
- Lesson: The action should possibly include a reasoning budget, not just a model name.

### 7.15 Route-To-Reason

- Paper: [arXiv 2505.19435](https://arxiv.org/abs/2505.19435)
- Data: Seven open models, four reasoning strategies, and seven reasoning datasets.
- Training target: Expected task performance and expected output tokens for every model–strategy pair.
- Selection: Jointly choose model and reasoning strategy.
- Reported outcome: Significant token reduction while preserving reasoning quality.
- Relevance: Direct foundation for adding `reasoning_mode` or `token_budget` to LFM2.5-ModelRouter actions.

### 7.16 RouteProfile

- Paper: [arXiv 2605.00180](https://arxiv.org/abs/2605.00180)
- Code/data: Linked from the paper through the UIUC project resources.
- Focus: Model-profile design rather than a single new router.
- Dimensions studied:
  - Organizational form.
  - Representation type.
  - Aggregation depth.
  - Trainable versus training-free configuration.
- Main lesson: Structured, query-level behavioral profiles outperform flat descriptions, particularly for cold-started new models.

### 7.17 Router-R1

- Paper/resources: [Router-R1](https://github.com/ulab-uiuc/Router-R1)
- Training data: Approximately 7K Natural Questions plus 7K HotpotQA questions.
- Candidate outputs: Each candidate is sampled repeatedly to estimate answer success.
- Router backbones: Qwen2.5-3B and Llama-3.2-3B variants.
- RL implementation: PPO using veRL in the reported implementation.
- Horizon: Up to four routing/tool steps.
- Reward: Formatting plus answer exact match plus an optional model/output cost term.
- Important detail: Main experiments may emphasize answer reward more than cost depending on the configured coefficient.
- Relevance: Blueprint for multi-round routing after the one-step system works.

### 7.18 xRouter

- Paper: [arXiv 2510.08439](https://arxiv.org/abs/2510.08439)
- Router: Qwen2.5-7B-Instruct.
- Data: Reasoning360 with difficulty estimated using pass-at-k behavior of a stronger Qwen model, plus conversational/factual augmentation.
- RL: DAPO, a GRPO-style policy optimization method, using veRL.
- Actions: Answer directly or call candidate models as tools, with a limited number of turns.
- Reward: Failed tasks receive no utility regardless of cheapness; successful outcomes receive a cost-adjusted reward.
- Important finding: Sophisticated multi-model behavior did not automatically emerge. Policies often converged toward simply choosing one model.
- Lesson: GRPO is not automatically superior for a small one-step router.

### 7.19 Learning to Route LLMs from Bandit Feedback — BaRP

- Paper: [arXiv 2510.07429](https://arxiv.org/abs/2510.07429)
- Data: RouterBench plus Natural Questions/HotpotQA-style outcome logs; full data is converted into simulated bandit feedback by revealing only the chosen action.
- Encoder: Frozen `all-MiniLM-L6-v2`.
- Policy: Small preference encoder and MLP decision head.
- Context: Query plus user quality/cost preference weights.
- Reward: Weighted quality minus normalized/clipped cost.
- Training: REINFORCE with minibatch baseline and entropy regularization; reported setup uses Adam around `1e-4`, batch size 32, and a single A100.
- Strength: One checkpoint can serve many user trade-offs.
- Limitation: Candidate actions are still fixed model identities.

### 7.20 Causal LLM Routing

- Paper: [arXiv 2505.16037](https://arxiv.org/abs/2505.16037)
- Data: RouterBench and SPROUT.
- Setting: Observational logs where only the deployed model's outcome is visible.
- Method:
  - Per-model outcome models.
  - Propensity prediction, including XGBoost in reported experiments.
  - Doubly robust counterfactual utility estimation.
  - Direct regret minimization using classification or softmax surrogates.
- Router representations: BERT-base or Llama-3.2-1B pooled features plus small MLPs.
- Strength: More realistic than assuming outcomes from every model are available after deployment.
- Requirement: Logging policy must preserve action probabilities and enough exploration/support for counterfactual estimation.

### 7.21 PILOT

- Paper: [Adaptive LLM Routing under Budget Constraints](https://arxiv.org/abs/2508.21141)
- Full name: Preference-prior Informed LinUCB for Adaptive Routing.
- Offline initialization: Human preference information such as Chatbot Arena.
- Online learning: LinUCB from success/failure bandit feedback.
- Budget control: Online multiple-choice knapsack formulation.
- Strength: Combines public preference priors with sparse feedback.
- Limitation: Finite-horizon and fixed-action assumptions differ from fully open-ended production serving.

### 7.22 ParetoBandit

- Paper: [arXiv 2604.00136](https://arxiv.org/abs/2604.00136)
- Data:
  - 11,983 prompts from MMLU, GSM8K, HellaSwag, BBH, ARC-Challenge, OpenBookQA, WinoGrande, TruthfulQA, and MBPP.
  - Complete outcomes for a small three-model portfolio, with another model used for onboarding experiments.
  - A held-out replay stream of 1,824 prompts in reported deployment experiments.
- Quality: Continuous LLM-judge rubric.
- Query representation: `all-MiniLM-L6-v2`, reduced to 25 PCA dimensions plus bias.
- Router: Per-model LinUCB.
- Production mechanisms:
  - Primal–dual dollar-budget pacer.
  - Geometric forgetting for non-stationarity.
  - Staleness-aware uncertainty.
  - Offline warm-start priors.
  - Runtime add/remove registry.
  - Forced exploration for a new model.
- Reported tests:
  - Price reduction.
  - Silent model-quality degradation.
  - Model addition.
  - Budget compliance.
- Critical implication: “Prices change and models arrive” alone is no longer a new research contribution.
- Opportunity: Replace generic MiniLM features and independent arms with a learned semantic query–model profile system that transfers knowledge to unseen arms from very few probes.

### 7.23 TRACE-Router

- Paper: [arXiv 2607.22465](https://arxiv.org/abs/2607.22465)
- Setting: Agentic tasks rather than independent chat turns.
- Routing: Select one backend for an entire task and update a contextual-UCB policy from terminal reward.
- Reward: Final task accuracy and latency.
- Evaluations include tool-use, coding, and terminal-style tasks.
- Important lesson: A response-level metric can be misleading. A model that is cheap per call may require more turns, fail tools, or force expensive recovery.

### 7.24 MTRouter

- Paper: [ACL 2026](https://aclanthology.org/2026.acl-long.2045/)
- Setting: Multi-turn model routing with conversation/tool history.
- Method: Lightweight outcome estimation over joint history–model representations, enabling turn-level routing without using a very large router model.
- Relevance: Possible second-stage extension once static single-turn routing works.

---

## 8. Cursor Router: What It Has That We Do Not

- Official article: [How Cursor Router chooses the right model for the task](https://cursor.com/blog/how-cursor-router-works)

Cursor reports building its router from hundreds of thousands of live development turns. Each datapoint contains the conversation signals available when routing and two important outcomes:

1. **Performance:** Inferred from what the developer does next. Moving to the next task is a strong positive signal; correcting the agent is a strong negative signal.
2. **Cost:** Computed from API pricing and actual token usage, including production effects such as cache misses caused by changing models.

Cursor's current approach includes:

- A continuous complexity/satisfaction predictor called Compass.
- A taxonomy of domains, tasks, and modifiers.
- Per-category comparisons of frontier models.
- A confidence threshold before routing away from the efficient baseline.
- An optimizer that selects the best traffic mixture under a budget.
- Live evaluation of user satisfaction, token usage, caching, and switching.
- Continuous iteration as models and traffic change.

### 8.1 What cannot be copied

- Their raw traffic.
- Their user-correction labels.
- Their real codebase/task context.
- Their online experiments.
- Their cache and switching economics.

### 8.2 What can be reproduced publicly

- Full-feedback offline pretraining.
- Synthetic non-stationary replay events.
- Model and family holdouts.
- Sparse new-model calibration.
- Bandit feedback where only the selected model's outcome is revealed.
- Code/task datasets with objective pass/fail outcomes.
- A small opt-in demo that later collects explicit thumbs-up/down or task success.

---

## 9. Formal Problem Definition

At request time `t`, the system observes:

- Query or task context: `x_t`.
- Candidate registry: `A_t`.
- Model/profile information: `z_m` for each candidate `m`.
- Current input/output/cached-token price table: `P_t`.
- Availability/rate-limit information: `v_t`.
- User preference: `w_t = (w_quality, w_cost, w_latency)`.
- Optional hard constraints: maximum cost, maximum latency, context requirement, privacy/local-only requirement, modality requirement.

The one-step action is:

```text
a_t = (model_id, reasoning_mode, output_budget)
```

The environment later produces:

- Quality/task reward `q_t`.
- Input tokens `n_in`.
- Output tokens `n_out`.
- Latency `l_t`.
- Provider success/failure.
- Optional delayed final task reward.

The router seeks to maximize expected quality while satisfying cost and latency preferences or constraints.

### 9.1 Runtime cost

```text
cost_t(m, x) =
    input_price_t[m]  * input_tokens(x)
  + output_price_t[m] * predicted_output_tokens(m, x)
  + cached_input_price_t[m] * cached_tokens
  + switching_or_cache_miss_penalty(previous_model, m)
  + fixed_provider_fee_if_any
```

Store raw token counts. Do not bake historical dollar cost permanently into the training label.

### 9.2 Preference-conditioned utility

One normalized utility form is:

```text
utility_t(m, x, w) =
    w_quality * calibrated_quality(m, x)
  - w_cost    * normalized_runtime_cost_t(m, x)
  - w_latency * normalized_latency(m, x)
  - failure_penalty * P(provider_failure | m, x)
  + exploration_bonus(m, x)
```

Hard constraints should be applied before utility ranking. For example, exclude a model if it cannot accept the context length or required image modality.

---

## 10. Proposed Architecture

### 10.1 Query encoder

Use `LiquidAI/LFM2.5-Encoder-350M` to encode:

- Current prompt.
- Optional recent conversation summary.
- Optional structured task tags.
- Optional required modalities/tools.

Initial experiments:

1. Freeze LFM and train only lightweight heads.
2. Fine-tune the last encoder blocks.
3. Full fine-tune.

This creates a useful ablation and reduces initial compute risk.

### 10.2 Model-profile encoder

A new candidate model must not be represented only by a learned integer ID.

Construct `z_m` from:

#### Static metadata

- Family/vendor.
- Architecture type: dense/MoE/recurrent/hybrid if known.
- Total and active parameters.
- Context length.
- Supported modalities.
- Tool/function-calling support.
- Quantization and serving backend.
- Open versus remote API.
- Reasoning modes or effort controls.
- Release/version date.

#### Behavioral probe statistics

- Correctness or judge score on a fixed anchor set.
- Per-domain success.
- Query-level result vector for selected anchors.
- Mean and distribution of output tokens.
- Mean and tail latency.
- Format/tool-call reliability.
- Refusal and provider-error rates.

#### Learned representation

Possible implementations:

1. MLP over structured statistics.
2. Set encoder over probe `(query_embedding, outcome)` pairs.
3. Attention from the current query to the model's probe history.
4. Low-rank behavioral embedding pretrained on RouterEval/EmbedLLM.

Recommended version one:

- Fixed anchor ordering.
- Behavioral vector with score, log output tokens, and latency per anchor.
- Missing-value mask.
- Small MLP projection to model-profile dimension.
- Static metadata concatenated after normalization.

Recommended research version:

- Query-conditioned set attention over a variable number of probe interactions.
- This allows experiments with 16, 32, 64, and 128 probes.

### 10.3 Interaction and prediction heads

Given query embedding `h_x`, model embedding `z_m`, mode embedding `r`, and budget embedding `b`, build interaction features such as:

```text
[h_x, z_m, h_x * z_m, |h_x - z_m|, r, b]
```

Heads:

- `quality_head`: Expected normalized quality or probability of success.
- `token_head`: Expected log output tokens; optionally quantiles.
- `latency_head`: Expected log latency; optionally p50/p95.
- `failure_head`: Provider or formatting failure probability.
- `uncertainty_head`: Aleatoric uncertainty or ensemble variance.

Do not use a fixed `num_models` softmax as the primary architecture. Score candidate configurations independently so the candidate list can change.

### 10.4 Runtime optimizer

The runtime optimizer:

1. Filters invalid/unavailable candidates.
2. Predicts quality, tokens, latency, failure, and uncertainty.
3. Reads current price data.
4. Computes utility for the selected user mode.
5. Adds an exploration bonus if online learning is enabled.
6. Enforces hard per-request or average-budget limits.
7. Selects the highest-utility valid action.

### 10.5 Online adapter

Version one should use a contextual bandit layered over the neural predictor:

- Discounted LinUCB.
- NeuralLinear/last-layer Bayesian regression.
- Discounted Thompson sampling.
- Per-model residual calibrator on top of the shared neural prior.

Recommended first implementation:

- Shared LFM predictor provides prior mean.
- Per-model linear residual head learns from online outcomes.
- Geometric forgetting handles drift.
- Uncertainty/upper-confidence bonus drives bounded exploration.
- A dual variable controls average dollar budget.

---

## 11. Dataset Schema to Build

Store the canonical data in Parquet. Provide lightweight JSONL exports for debugging.

### 11.1 Query table

```text
query_id: string
source_dataset: string
source_split: string
task_family: string
task_name: string
prompt: string
conversation_json: optional string/json
ground_truth_json: optional string/json
metric_name: string
modality: text | image | video | time_series | mixed
input_length_chars: int
input_tokens_by_tokenizer: optional map
timestamp_or_release_cutoff: optional datetime
license_tag: string
```

### 11.2 Model registry table

```text
model_id: stable internal string
provider: string
upstream_model_name: string
family: string
version: string
release_date: optional date
total_parameters: optional float
active_parameters: optional float
architecture_type: optional string
context_length: optional int
modalities: list[string]
supports_tools: bool
supports_reasoning_modes: bool
reasoning_modes: list[string]
quantization: optional string
serving_backend: optional string
is_local: bool
license: optional string
metadata_source_urls: list[string]
```

### 11.3 Outcome table

Each row represents one query–action execution.

```text
execution_id: string
query_id: string
model_id: string
reasoning_mode: optional string
requested_output_budget: optional int
run_seed: optional int
temperature: optional float
response_text: optional string
raw_metric_score: float
normalized_quality: float
success: optional bool
judge_model: optional string
judge_prompt_version: optional string
input_tokens: int
output_tokens: int
cached_input_tokens: optional int
latency_ms: optional float
time_to_first_token_ms: optional float
provider_error: optional string
finish_reason: optional string
recorded_cost_usd: optional float
price_snapshot_id: optional string
execution_timestamp: optional datetime
```

### 11.4 Price history table

```text
price_snapshot_id: string
effective_from: datetime
effective_to: optional datetime
provider: string
model_id: string
input_usd_per_million: float
cached_input_usd_per_million: optional float
output_usd_per_million: float
batch_discount: optional float
source_url: string
verified_at: datetime
```

### 11.5 Probe profile table

```text
profile_version: string
model_id: string
anchor_query_id: string
anchor_group: string
probe_index: int
observed_quality: optional float
observed_output_tokens: optional int
observed_latency_ms: optional float
observed_failure: optional bool
missing_mask: bool
```

### 11.6 Online routing log

```text
event_id: string
timestamp: datetime
query_id_or_hash: string
available_actions: list[string]
selected_action: string
selection_probability: float
policy_version: string
preference_vector: struct
hard_budget: optional float
predicted_quality: float
predicted_cost: float
predicted_latency: float
uncertainty: float
observed_quality: optional float
observed_cost: optional float
observed_latency: optional float
terminal_task_reward: optional float
feedback_delay_ms: optional float
```

The selection probability is essential for unbiased/off-policy evaluation.

### 11.7 Example JSONL row

```json
{
  "query_id": "xroutebench:gsm8k:000123",
  "prompt": "A shop sold ...",
  "task_family": "math",
  "model_id": "qwen3-next-80b-a3b-instruct",
  "reasoning_mode": "standard",
  "raw_metric_score": 1.0,
  "normalized_quality": 1.0,
  "input_tokens": 164,
  "output_tokens": 412,
  "latency_ms": 2840.0,
  "price_snapshot_id": "prices:2026-08-20",
  "recorded_cost_usd": 0.000642,
  "provider_error": null
}
```

---

## 12. Data Preparation Pipeline

### 12.1 Ingestion

Create one adapter per source:

```text
src/data/adapters/xroutebench.py
src/data/adapters/llmrouterbench.py
src/data/adapters/routerbench.py
src/data/adapters/sprout.py
src/data/adapters/embedllm.py
src/data/adapters/r2bench.py
```

Each adapter should output the canonical query, model, and outcome tables.

### 12.2 Quality normalization

Raw metrics are not directly comparable. Accuracy, F1, code-pass rate, judge score, retrieval score, and geometry score can have different ranges and calibration.

Required approaches:

1. Preserve the raw score and metric name.
2. Normalize per dataset/task.
3. Prefer objective pass/fail when available.
4. For continuous metrics, test:
   - Min/max normalization from documented metric bounds.
   - Rank/percentile transform within task.
   - Z-score followed by sigmoid.
   - Calibrated probability of meeting a task-specific success threshold.
5. Never compare an uncalibrated MATH exact-match value directly with an arbitrary LLM-judge score.

Recommended main target:

```text
P(action meets task-specific success criterion | query, model profile)
```

Continuous quality can be a secondary head.

### 12.3 Token and latency normalization

- Predict `log1p(output_tokens)` with Huber loss.
- Predict `log1p(latency_ms)` or quantiles.
- Include provider/backend information when latency comes from different systems.
- Separate time-to-first-token and total latency when available.
- Do not pretend latency across unrelated hardware/providers is perfectly comparable.

### 12.4 Deduplication and leakage checks

- Exact prompt hash.
- Normalized-text hash.
- Fuzzy/embedding near-duplicate detection.
- Benchmark/source IDs.
- Model family leakage.
- Synthetic augmentation lineage.
- Ensure anchor/probe queries are disjoint from final test queries.
- Ensure held-out models are not represented through duplicated aliases or quantizations unless that is an explicit family-transfer experiment.

### 12.5 Splits

Create several independent split definitions:

#### Prompt-IID split

Basic train/validation/test by query. Useful only as the easiest benchmark.

#### Task-OOD split

Hold out entire task datasets or task families.

#### Model-held-out split

Hold out candidate models completely during router training. Provide only the allowed probe set at onboarding.

#### Family-held-out split

Hold out an entire model family/provider to avoid easy alias/version transfer.

#### Temporal split

Train only on models/data available before a cutoff; test on models released later.

#### Joint OOD split

New model plus new task distribution. This is the hardest and most realistic setting.

### 12.6 Full feedback to bandit replay

For offline supervised training, all candidate outcomes are visible.

For online evaluation:

1. Present one query at a time.
2. Let the router select one candidate.
3. Reveal only that candidate's stored outcome.
4. Update the online adapter.
5. Retain hidden outcomes solely to calculate oracle regret after the decision.

This prevents accidentally training the online algorithm with counterfactual outcomes it would never observe in deployment.

---

## 13. Behavioral Anchor-Set Design

The anchor set is central to the cold-start contribution.

### 13.1 Purpose

When a new model arrives, do not rerun the entire training dataset. Run a small, fixed, diverse probe set and derive a model fingerprint.

### 13.2 Candidate sizes

Evaluate:

- 0 probes: metadata/text-only zero shot.
- 8 probes.
- 16 probes.
- 32 probes.
- 64 probes.
- 128 probes.
- 256 probes.
- 500 probes as an expensive ICL-Router-style comparison.

### 13.3 Probe categories

The probe pool should include:

- Simple and difficult math.
- General knowledge.
- Logic.
- Code generation and debugging.
- Instruction following.
- Long-context retrieval.
- Tool/function-call formatting.
- Safety/refusal behavior where relevant.
- Short and long expected outputs.
- Multilingual examples if within scope.
- Visual/multimodal tasks only for models that support them.

### 13.4 Selecting probes

Compare:

1. Uniform random.
2. Stratified random by domain and difficulty.
3. K-means/medoid selection in query-embedding space.
4. Maximal diversity/farthest-point sampling.
5. Information-gain or active-selection probes.
6. Learned probes optimized for model discrimination.

Potential research contribution:

> Learn the smallest probe set that preserves downstream routing regret.

### 13.5 Preventing leakage

- Probe queries must not appear in routing test traffic.
- If probes come from the same benchmark, hold out exact and near duplicates.
- Report whether probes use ground-truth evaluation or an LLM judge.
- Maintain a public versioned anchor-set manifest.

---

## 14. Supervised Training Objectives

### 14.1 Quality loss

For binary success:

```text
L_quality = BCE(predicted_success_probability, success_label)
```

For continuous normalized quality:

```text
L_quality_reg = Huber(predicted_quality, normalized_quality)
```

Use both if possible.

### 14.2 Token loss

```text
L_tokens = Huber(predicted_log1p_output_tokens, log1p(output_tokens))
```

Optional quantile heads can estimate uncertainty and tail cost.

### 14.3 Latency loss

```text
L_latency = Huber(predicted_log1p_latency, log1p(latency_ms))
```

Mask missing latency values.

### 14.4 Failure loss

```text
L_failure = BCE(predicted_failure_probability, provider_or_format_failure)
```

### 14.5 Pairwise utility-ranking loss

Sample preference vectors `w` during training. For two actions `a_i` and `a_j` on the same query, calculate their runtime utility using a sampled price snapshot and preference vector.

```text
L_rank = -log sigmoid(predicted_U_i - predicted_U_j)
```

when observed utility says `a_i` should beat `a_j`.

This helps train one checkpoint for Intelligence, Balanced, Cost, and arbitrary continuous preferences.

### 14.6 Calibration loss

Evaluate temperature scaling, isotonic regression, or a held-out calibration head. Accurate uncertainty is essential for safe exploration and “cheapest model likely to succeed” decisions.

### 14.7 Optional contrastive loss

Encourage query representations to align with successful model profiles and separate unsuccessful ones, similar to RouterDC.

### 14.8 Combined objective

```text
L_total =
    lambda_q * L_quality
  + lambda_qr * L_quality_reg
  + lambda_t * L_tokens
  + lambda_l * L_latency
  + lambda_f * L_failure
  + lambda_r * L_rank
  + lambda_c * L_contrastive
```

Tune weights on validation Pareto performance, not only prediction MSE.

---

## 15. Preference Modes

Do not train three completely separate models unless used as an ablation.

### 15.1 Intelligence

- Very high quality weight.
- Small but nonzero cost/latency weight.
- May use expensive model only when predicted quality improvement is meaningful.

### 15.2 Balanced

- Moderate quality, cost, and latency weights.
- Prefer actions close to the Pareto knee.

### 15.3 Cost

- Apply a minimum success threshold.
- Among candidates meeting the threshold, choose the lowest predicted runtime cost.
- If no candidate meets the threshold, select the action maximizing success per unit cost or escalate according to configured policy.

### 15.4 Continuous preference conditioning

Sample weights during training, for example from a Dirichlet distribution. At inference, predefined modes are only named presets over a continuous preference space.

---

## 16. Price Changes

### 16.1 Correct design

Price is dynamic environment state.

- Keep input and output token predictions in the model.
- Keep price in a versioned external table.
- Recompute expected dollar cost at every decision.
- A new price becomes effective immediately.

### 16.2 What may still need learning

A price change alone requires no retraining. However, provider or model changes may also alter:

- Output-length distribution.
- Latency.
- Cached-token behavior.
- Reliability.
- Actual answer quality.

Those changes require online outcome updates, not simply a price-table update.

### 16.3 Simulated price events

Include at least:

- 10× price cut for an expensive model.
- 2× price increase for the current favorite.
- Input-only price change.
- Output-only price change.
- Cached-input discount introduction.
- Temporary promotional pricing.

Measure how rapidly traffic allocation changes and whether budget constraints remain satisfied.

---

## 17. New Models and Model Removal

### 17.1 New-model onboarding

1. Register static metadata.
2. Run the chosen number of anchor probes.
3. Construct initial behavioral profile.
4. Initialize shared-neural prior predictions.
5. Initialize online residual statistics with uncertainty.
6. Perform bounded forced exploration.
7. Allow UCB/Thompson policy to discover the model's niche.

### 17.2 Forced exploration

Evaluate a fixed number such as 10, 20, or 50 live pulls, and uncertainty-based alternatives. Expensive models must respect the global budget during exploration.

### 17.3 Model removal

Removing a model should be a registry operation. The scoring network must not assume a fixed number or ordering of candidate classes.

### 17.4 Version updates

Treat a silently updated API model carefully:

- If provider exposes a new version ID, register it as a related new model.
- If version is hidden, use drift detection on reward/output/latency residuals.
- Decay old observations using geometric forgetting.

---

## 18. Online Learning

### 18.1 Why contextual bandits fit version one

At deployment, only the selected model's outcome is observed. This is a contextual bandit, not ordinary supervised learning.

### 18.2 Recommended policy

Start with a shared neural prior plus discounted per-model linear residuals:

```text
predicted_reward = neural_prior(query, model_profile) + linear_residual_model(query_features)
```

UCB score:

```text
score = predicted_utility + alpha * uncertainty - dynamic_budget_penalty
```

Update only the selected action using the observed outcome.

### 18.3 Non-stationarity

Apply geometric forgetting:

```text
A_m <- gamma * A_m + x x^T
b_m <- gamma * b_m + reward * x
```

Test multiple effective memory horizons.

### 18.4 Budget pacing

Maintain a dual variable that increases after overspending and decreases after underspending:

```text
lambda_budget <- clip(
    lambda_budget + eta * (recent_average_cost / target_cost - 1),
    0,
    lambda_max
)
```

The runtime score then subtracts `lambda_budget * cost`.

### 18.5 Offline logging requirements

Every action log should include:

- Candidate set.
- Chosen action.
- Selection probability.
- Policy version.
- Predicted outcomes.
- Preference vector.
- Observed outcome and feedback delay.

Without action probabilities, reliable inverse-propensity or doubly robust evaluation becomes difficult.

---

## 19. Why GRPO Is Not the First Step

GRPO/PPO is appropriate when the router is itself a sequential generative policy with actions such as:

- Answer directly.
- Call model A.
- Inspect answer.
- Call model B for verification.
- Change reasoning budget.
- Aggregate.
- Stop.

For one-step model selection, supervised outcome prediction plus a contextual bandit is:

- Simpler.
- Cheaper.
- Easier to debug.
- Easier to calibrate.
- More suitable for a bidirectional encoder.
- Easier to compare against established baselines.

Router-R1 uses PPO for multi-round decisions. xRouter uses DAPO/GRPO-style optimization, but reports that complex orchestration can degenerate into simple choose-one behavior. RL should be an extension after a strong one-step baseline exists.

### 19.1 Possible later RL action space

```text
{ANSWER_SELF, CALL_MODEL_i(mode, budget), VERIFY_WITH_j, STOP_AND_RETURN}
```

### 19.2 Later RL reward

```text
reward =
    terminal_task_success
  - lambda_cost * total_dollar_cost
  - lambda_latency * total_wall_clock_time
  - lambda_calls * number_of_external_calls
  - failure_penalty
```

Failure should be gated strongly so the policy cannot earn a good reward merely by being cheap and incorrect.

---

## 20. Non-Stationary Replay Simulator

Build the simulator before the online algorithm.

### 20.1 Event types

```text
PRICE_CHANGE
QUALITY_REGRESSION
QUALITY_IMPROVEMENT
LATENCY_SHIFT
PROVIDER_FAILURE_SPIKE
MODEL_ADD
MODEL_REMOVE
TRAFFIC_DISTRIBUTION_SHIFT
USER_PREFERENCE_SHIFT
BUDGET_CHANGE
```

### 20.2 Required core scenario

Example 10,000-request stream:

1. Requests 0–1,999: Stable portfolio.
2. At 2,000: Expensive reasoning model receives 5× output-price cut.
3. At 4,000: Previously strong code model loses 15% task success.
4. At 6,000: Completely held-out new model is added with only 64 anchor probes.
5. At 8,000: Current cheapest model becomes unavailable.

### 20.3 Traffic drift

Change query mixture over time:

- General QA-heavy.
- Coding-heavy.
- Math/reasoning-heavy.
- Long-context-heavy.
- Tool-use-heavy.

### 20.4 Feedback visibility

Only reveal the selected model's outcome to the policy. Use complete stored outcomes solely for calculating oracle performance and regret.

---

## 21. Evaluation Protocol

### 21.1 Offline prediction metrics

- AUROC/AUPRC for success.
- Brier score.
- Expected calibration error.
- Quality MAE/Spearman correlation.
- Output-token MAE on log scale.
- Latency MAE and p95 error.
- Model recall: whether the router identifies the only successful model.

### 21.2 Routing metrics

- Average normalized quality.
- Success rate.
- Dollar cost per request.
- Input/output tokens per request.
- Average and p95 latency.
- Router inference latency.
- Cost savings at matched quality.
- Quality gain at matched cost.
- Pareto-frontier distance.
- Pareto hypervolume.

### 21.3 Non-stationary metrics

- Cumulative regret versus dynamic oracle.
- Sliding-window regret.
- Adaptation half-life after an event.
- Requests required for new-model adoption.
- Cold-start regret.
- Budget violation magnitude/frequency.
- Recovery time after quality regression.
- Exploration cost.
- Traffic allocation entropy.
- Stability/churn in selected model.

### 21.4 Generalization metrics

- Held-out query performance.
- Held-out task performance.
- Held-out model performance.
- Held-out model family performance.
- Temporal/new-release performance.
- Joint new-model/new-task performance.

### 21.5 Statistical reporting

- At least five random seeds for lightweight experiments.
- Confidence intervals through bootstrap over queries/streams.
- Paired tests where the same replay stream is used.
- Report total API/compute cost.
- Report model and price snapshot dates.

---

## 22. Required Baselines

### 22.1 Simple baselines

- Random valid model.
- Cheapest model.
- Largest/most expensive model.
- Best single model chosen on training/validation.
- Per-domain best model.
- Oracle best-quality model.
- Oracle cheapest successful model.

### 22.2 Learned baselines

- Logistic/MLP classifier on frozen MiniLM embeddings.
- RouteLLM matrix-factorization router.
- HybridLLM-style binary classifier where applicable.
- RouterDC-style query/model contrastive model.
- EmbedLLM-style matrix-factorization predictor.
- GraphRouter or a simplified graph/profile baseline.
- LFM query encoder with fixed learned model IDs.
- LFM query encoder with textual model descriptions.
- LFM with behavioral profiles but no online adapter.

### 22.3 Online baselines

- Epsilon-greedy.
- Standard LinUCB.
- Discounted LinUCB.
- Thompson sampling.
- PILOT-style preference prior.
- ParetoBandit-style budget-paced non-stationary bandit.

The key comparison is not “LFM versus random.” It is:

> LFM shared semantic prior + sparse behavioral profile versus a strong ParetoBandit/MiniLM system under unseen-model cold start.

---

## 23. Ablation Studies

At minimum:

1. No model profile; fixed learned ID only.
2. Text metadata only.
3. Domain-aggregate behavioral profile.
4. Query-level probe profile.
5. Structured metadata + behavioral profile.
6. Different probe counts.
7. Random versus diverse versus learned probes.
8. Frozen LFM versus partial fine-tune versus full fine-tune.
9. No ranking loss.
10. No preference conditioning.
11. Historical price inside training label versus runtime price table.
12. No uncertainty bonus.
13. No forgetting.
14. No offline prior.
15. No forced exploration.
16. Response-level reward versus terminal task reward when agent data is available.
17. Model-only action versus model + output-budget action.

---

## 24. Research Hypotheses

### H1: Sparse behavioral profiles beat textual metadata

A query-conditioned behavioral profile from 32–128 probes should reduce regret on unseen models compared with a name/description-only representation.

### H2: Shared semantic priors reduce cold-start exploration

The LFM predictor should allow a new model to reach useful traffic allocation in fewer online pulls than an independent-arm bandit initialized without cross-model knowledge.

### H3: Runtime price separation eliminates unnecessary retraining

If token/latency outputs are predicted separately and live prices are injected at decision time, pure price changes should require zero gradient updates while preserving the correct quality–cost ordering.

### H4: Preference conditioning produces a smoother frontier

A single model trained across sampled weight vectors should yield a better and more continuous Pareto frontier than three independently trained fixed-mode classifiers.

### H5: Reasoning-budget actions improve efficiency

Selecting `(model, output budget)` should dominate model-only selection on reasoning tasks because quality and cost vary substantially with allowed reasoning length.

### H6: Task-level reward changes routing decisions

For agentic tasks, a model that is more expensive per call can be cheaper overall if it finishes in fewer turns and avoids recovery.

---

## 25. Recommended Implementation Phases

### Phase 0 — Repository and reproducibility

Deliverables:

- Python package.
- `uv` or Poetry environment.
- Config system.
- Deterministic seeds.
- Dataset manifests.
- Experiment logging.
- Unit tests.
- CI for formatting, type checks, and small tests.

### Phase 1 — Data audit and canonical tables

Start only with xRouteBench.

Deliverables:

- Download script.
- Schema audit report.
- Canonical Parquet tables.
- Data statistics notebook/script.
- Deduplication report.
- Reproducible prompt/model splits.
- Best-single and oracle baselines.

### Phase 2 — Frozen-encoder offline router

Deliverables:

- Frozen LFM query embeddings.
- Simple learned model-ID baseline.
- Quality, output-token, and latency heads.
- Runtime price optimizer.
- Intelligence/Balanced/Cost presets.
- Pareto plots.

### Phase 3 — Behavioral model profiles

Deliverables:

- Anchor selection.
- Model-held-out splits.
- Probe-profile encoder.
- Probe-count learning curves.
- Comparison with text-only profiles and ID embeddings.

### Phase 4 — Non-stationary simulator

Deliverables:

- Event-driven replay environment.
- Price/model/quality/traffic events.
- Dynamic oracle.
- Regret and budget metrics.

### Phase 5 — Online adapter

Deliverables:

- Discounted LinUCB or NeuralLinear adapter.
- Budget pacer.
- Forced exploration.
- Drift recovery and new-model experiments.
- ParetoBandit-style baseline.

### Phase 6 — LLMRouterBench and R2-Bench augmentation

Deliverables:

- Current flagship/code/tool-use training/evaluation.
- Model + reasoning-budget action support.
- Family-held-out and temporal tests.

### Phase 7 — Agent-task extension

Optional, only after prior phases are strong:

- Tau-squared Bench, SWE-Bench, Terminal-Bench, or similar tasks.
- Sticky task-level routing.
- Delayed terminal reward.
- Cache/switch penalty.
- TRACE/MTRouter comparison.

### Phase 8 — Multi-round RL

Optional:

- Generative policy router.
- PPO or GRPO-style training.
- Verification/aggregation actions.
- Terminal task reward with cost and latency penalties.

---

## 26. Suggested Repository Structure

```text
lfm-churn-router/
├── README.md
├── LICENSE
├── CITATION.cff
├── pyproject.toml
├── Makefile
├── configs/
│   ├── data/
│   ├── model/
│   ├── training/
│   ├── simulation/
│   └── experiments/
├── data/
│   ├── manifests/
│   ├── raw/                 # gitignored
│   ├── interim/             # gitignored
│   └── processed/           # gitignored or DVC/LFS
├── src/churnrouter/
│   ├── data/
│   │   ├── schemas.py
│   │   ├── normalize.py
│   │   ├── splits.py
│   │   ├── probes.py
│   │   └── adapters/
│   ├── models/
│   │   ├── lfm_query_encoder.py
│   │   ├── model_profile_encoder.py
│   │   ├── interaction.py
│   │   ├── prediction_heads.py
│   │   └── losses.py
│   ├── routing/
│   │   ├── registry.py
│   │   ├── constraints.py
│   │   ├── utility.py
│   │   ├── optimizer.py
│   │   └── policies.py
│   ├── online/
│   │   ├── linucb.py
│   │   ├── discounted_linucb.py
│   │   ├── budget_pacer.py
│   │   ├── drift.py
│   │   └── logging.py
│   ├── simulator/
│   │   ├── environment.py
│   │   ├── events.py
│   │   ├── replay.py
│   │   └── oracle.py
│   ├── evaluation/
│   │   ├── prediction_metrics.py
│   │   ├── routing_metrics.py
│   │   ├── pareto.py
│   │   ├── regret.py
│   │   └── plots.py
│   └── cli.py
├── scripts/
│   ├── download_xroutebench.py
│   ├── audit_xroutebench.py
│   ├── build_canonical_dataset.py
│   ├── train_offline.py
│   ├── build_profiles.py
│   ├── run_static_eval.py
│   └── run_churn_simulation.py
├── tests/
│   ├── test_schemas.py
│   ├── test_costs.py
│   ├── test_splits.py
│   ├── test_registry.py
│   ├── test_budget_pacer.py
│   └── test_replay.py
├── notebooks/
├── reports/
│   ├── figures/
│   └── tables/
└── docs/
    ├── DATASETS.md
    ├── METHODS.md
    ├── REPRODUCIBILITY.md
    └── MODEL_CARD.md
```

---

## 27. Technology Choices

Recommended starting stack:

- Python 3.11 or 3.12 after verifying model compatibility.
- PyTorch.
- Hugging Face Transformers/Datasets.
- `trust_remote_code=True` only for the Liquid model and with the repository revision pinned.
- PyArrow/Polars for Parquet transformation.
- Pydantic or dataclasses for canonical schemas.
- Hydra or simple YAML configs.
- Weights & Biases, MLflow, or local JSON/Parquet experiment logs.
- scikit-learn for calibration, PCA, and simple baselines.
- LightGBM/XGBoost for strong non-neural baselines.
- pytest, Ruff, and mypy/pyright.
- Optional DVC for large data manifests.

Do not require a web dashboard for the research MVP. Generate reproducible CSV/Parquet tables and publication-quality plots first.

---

## 28. Compute Strategy

### 28.1 Cheapest starting point

- Download and audit data on CPU.
- Train linear/LightGBM and frozen-embedding baselines first.
- Precompute query embeddings once.
- Use smaller dataset slices to validate pipelines.

### 28.2 LFM training

Because the encoder is only approximately 350M parameters:

- Frozen encoder plus heads should be easy on a single modern GPU.
- Partial/full fine-tuning may fit on a 24–32GB GPU with mixed precision and gradient accumulation, depending on context length and batch size.
- Cloud CUDA hardware may be operationally simpler than local AMD for initial reproducibility.
- Do not rent H100s before the data pipeline and baseline metrics are correct.

### 28.3 Full-feedback cost

The public datasets already contain model outputs. Do not rerun all models initially. Only spend inference/API budget on:

- Verifying a small sample.
- Creating new-model probe profiles.
- Later adding newly released models.
- Agentic evaluation not already present.

---

## 29. Data and Research Risks

### 29.1 Benchmark contamination

Modern models may have trained on benchmark questions. Routing results measure observed benchmark behavior, not uncontaminated intelligence.

Mitigation:

- Use newer/live benchmarks.
- Temporal splits.
- Code/tool execution.
- Private generated test sets if carefully constructed.
- Report contamination limitations honestly.

### 29.2 Metric inconsistency

Different datasets use different success metrics.

Mitigation:

- Preserve raw metrics.
- Normalize per task.
- Report per-domain results.
- Avoid one unexplained global “intelligence score.”

### 29.3 LLM judge bias

Judges may favor style, verbosity, family, or their own answers.

Mitigation:

- Prefer objective evaluation.
- Use multiple judges for open-ended tasks.
- Blind model identity.
- Validate judge agreement on a human-labeled subset.

### 29.4 Price staleness

Historical dataset prices become wrong.

Mitigation:

- Recalculate from raw token counts and a versioned price table.
- Record verification dates and sources.

### 29.5 Latency comparability

Latency depends on hardware, provider load, region, batching, and caching.

Mitigation:

- Preserve backend/provider metadata.
- Evaluate latency within consistent serving settings when possible.
- Report quality–cost results separately from latency results.

### 29.6 Model alias/version ambiguity

Provider names may silently point to updated weights.

Mitigation:

- Stable internal IDs.
- Version and date fields.
- Behavioral drift detection.
- Never overwrite historical outcomes silently.

### 29.7 Off-policy bias

Production logs expose only chosen actions.

Mitigation:

- Log selection propensities.
- Ensure exploration/support.
- Use inverse propensity or doubly robust estimators.
- Do not treat missing counterfactual outcomes as failures.

### 29.8 Reward hacking

An optimizer may learn to be cheap by choosing models that fail quickly or produce short incomplete answers.

Mitigation:

- Strongly gate utility on success.
- Use terminal task reward where possible.
- Add reliability/failure penalties.

### 29.9 Data licenses

Different benchmark, response, and model data have different licenses.

Mitigation:

- Create a source/license manifest.
- Avoid republishing restricted responses.
- Release transformation scripts when raw redistribution is restricted.

---

## 30. What a Strong Result Would Look Like

A compelling result is not merely “our router saves 40%.” It should demonstrate:

1. Comparable or improved matched-cost quality on held-out tasks.
2. Strong calibration.
3. Meaningful model-family holdout performance.
4. A new model becomes useful after only 32–64 probes and limited online pulls.
5. Pure price changes alter routing instantly without retraining.
6. Quality regression is detected and traffic is rerouted.
7. Average budget stays within target.
8. Router CPU/GPU latency is negligible compared with downstream generation.
9. Gains remain over a strong ParetoBandit-style baseline.

The signature figure should be a time-series plot showing:

- Model traffic share.
- Quality.
- Cost.
- Dynamic regret.
- Vertical markers for price cut, quality regression, new-model arrival, and model removal.

A second key plot should show routing regret versus number of new-model anchor probes.

---

## 31. Possible Paper Framing

### Title options

- **LFM2.5-ModelRouter: Sparse Cold-Start Routing for Evolving Model Portfolios**
- **Probe, Price, Route: Small-Encoder Routing Under Model Churn**
- **Cold-Starting New LLMs with Behavioral Fingerprints**
- **A 350M Router for Non-Stationary Model Markets**

### Abstract skeleton

```text
Large-language-model routers are commonly trained over a fixed candidate set
and evaluated under static prices. Production portfolios violate both
assumptions: models are added and removed, providers change prices, and model
quality can drift. We introduce LFM2.5-ModelRouter, a compact routing framework
that combines a 350M bidirectional query encoder with structured behavioral
model profiles, live price-conditioned optimization, and discounted online
adaptation. New models are represented from a small probe set rather than a
learned identity. On [datasets], under model-, family-, and task-held-out
evaluation plus controlled price/quality/model churn, our method [main result].
It achieves [quality/cost result], onboards new models with [N] probes, and
recovers from distribution shifts within [K] requests while respecting a
dollar-denominated budget.
```

### Honest novelty statement

ParetoBandit already introduces budget-paced online adaptation to prices, quality drift, and model arrival. ZeroRouter, Scope, ICL-Router, RouteProfile, GraphRouter, and R2-Router address new-model representation or flexible actions. The proposed novelty must be demonstrated as the combination of:

- A compact shared semantic encoder.
- Sparse query-level behavioral fingerprinting.
- Strong held-out-family cold start.
- Preference-conditioned runtime cost/latency selection.
- Non-stationary adaptation with fewer new-model samples.

---

## 32. Open-Source Deliverables

- Canonical routing dataset builder.
- Versioned dataset manifest.
- Public anchor probe set.
- Trained router configuration or weights if license permits.
- Model-profile generator.
- Versioned price-table format.
- Non-stationary replay simulator.
- Strong baselines.
- Reproducible experiment configs.
- Static evaluation report.
- Churn evaluation report.
- Model card.
- Research paper/preprint.
- Short interactive demo after the research pipeline is stable.

---

## 33. X/Twitter and Job-Application Story

The eventual public story should be evidence-driven:

```text
LLM routers become stale whenever prices change or a new model launches.

I trained a 350M Liquid encoder to predict query–model compatibility from
sparse behavioral fingerprints, while prices remain live runtime inputs.

In a replay with price cuts, quality regression, model arrival, and model
removal, the router onboarded an unseen model with only N probes and recovered
within K requests while respecting the cost budget.

Code, data pipeline, simulator, and results: [link]
```

Do not tweet before there is:

- A reproducible chart.
- A meaningful baseline.
- A held-out-model result.
- A clear limitation statement.

For an ML research application, emphasize:

- Literature review.
- Formal problem formulation.
- Dataset construction.
- Leakage-aware splits.
- Calibration and uncertainty.
- Strong baselines.
- Ablations.
- Non-stationary evaluation.
- Reproducibility and honest negative findings.

---

## 34. Exact First Tasks for Codex

The next coding session should perform these tasks in order.

### Task 1: Create the repository skeleton

- Initialize the directory structure in Section 26.
- Add `pyproject.toml`, Ruff, pytest, and type checking.
- Add a minimal README describing the research question without claiming results.

### Task 2: Inspect xRouteBench

- Read the current dataset card and repository.
- Record file names, configs, splits, row counts, columns, dtypes, and missingness.
- Download a small sample first.
- Produce `reports/xroutebench_audit.md` and a machine-readable schema snapshot.
- Confirm license and redistribution conditions.

### Task 3: Implement canonical schemas

- Query table.
- Model registry.
- Outcome table.
- Price history.
- Probe profiles.
- Online route logs.
- Add validation tests.

### Task 4: Build simple baselines before LFM

- Cheapest.
- Best single.
- Per-domain best.
- Oracle best quality.
- Oracle cheapest successful.
- Logistic/MLP on frozen sentence embeddings.
- Produce first Pareto table and plot.

### Task 5: Add LFM embeddings

- Pin model revision.
- Test CPU/GPU inference.
- Cache prompt embeddings.
- Train only small heads first.
- Verify the LFM model's license before planning weight publication.

### Task 6: Add dynamic price recomputation

- Preserve raw input/output token counts.
- Implement versioned price snapshots.
- Test that changing only the price table changes routing without modifying weights.

### Task 7: Create model-held-out experiments

- Choose four held-out models.
- Ensure aliases/family leakage are documented.
- Construct 16/32/64/128-probe profiles.
- Compare ID-only, metadata-only, and behavioral-profile approaches.

### Task 8: Build churn simulator

- Implement event types.
- Dynamic oracle.
- Reveal selected-arm outcomes only.
- Add regret, budget, and recovery metrics.

### Task 9: Add online bandit

- Discounted LinUCB baseline.
- Budget pacer.
- New-model forced exploration.
- LFM neural-prior residual version.

### Task 10: Run ablations and write the report

- Use versioned experiment configs.
- Save raw run outputs.
- Generate publication-quality figures from saved results.
- Report negative results.

---

## 35. Prompt to Give the Next Codex Session

```text
Read docs/RESEARCH_HANDOFF.md completely before acting.

We are building LFM2.5-ModelRouter, a research project using LiquidAI's
LFM2.5-Encoder-350M to route prompts among changing LLM portfolios under
quality, cost, and latency objectives. Prices must remain runtime inputs; new
models must be represented from sparse behavioral probes rather than fixed
softmax classes. The online component will use bandit feedback and handle
quality/model drift.

Do not build the full model yet. Start with Phase 0 and Phase 1 only:

1. Inspect the current workspace and preserve unrelated files.
2. Create a clean repository skeleton.
3. Inspect the current xRouteBench dataset/repository and verify its actual
   schema, splits, files, row counts, license, and download method.
4. Implement canonical data schemas and an xRouteBench adapter.
5. Add tests for schema validation, price recomputation, and leakage-safe
   splits.
6. Produce a dataset audit report and propose the exact first baseline
   experiment.

Do not start expensive model training or API inference. Ask only if a choice
would materially change the data model or authorization scope.
```

---

## 36. Decisions That Can Wait

Do not block Phase 1 on these:

- Exact final project name.
- Exact paper venue.
- Web demo design.
- GRPO versus PPO for a later sequential policy.
- Which commercial APIs to add.
- Final number of user modes.
- Whether to support multimodal data in the first release.

---

## 37. Decisions Required Before Full Training

Before Phase 2/3 training, decide:

- Exact xRouteBench scenarios included in the first study.
- Whether version one is text-only.
- Held-out models and held-out families.
- Probe-set construction algorithm.
- Quality normalization strategy.
- LFM frozen/partial/full fine-tune variants.
- Local versus cloud compute.
- Which weights/artifacts licenses allow publishing.

---

## 38. Definition of Done for the Research MVP

The MVP is complete when all of the following are true:

- Canonical xRouteBench pipeline is reproducible.
- Dataset and license audit is documented.
- At least five simple/learned baselines run end to end.
- LFM offline predictor estimates quality and token usage.
- Current prices are injected at runtime.
- Intelligence/Balanced/Cost preferences work without retraining.
- At least one model-held-out experiment exists.
- New-model profiles are evaluated across multiple probe counts.
- Non-stationary replay includes price change, quality regression, model addition, and model removal.
- Online adapter receives only selected-arm outcomes.
- Dynamic regret, budget compliance, recovery time, and Pareto metrics are reported.
- Results are compared with a strong discounted-LinUCB/ParetoBandit-style baseline.
- Repository includes tests, configs, seeds, raw result artifacts, and figure-generation scripts.
- README states limitations and does not imply access to Cursor data.

---

## 39. Final Recommendation

Build this project, but do not position it as “a router that balances intelligence and cost.” That problem is too broad and already crowded.

Position it as:

> **A small Liquid encoder that learns transferable query–model compatibility from sparse behavioral fingerprints, with live price optimization and online adaptation under model churn.**

Start with xRouteBench, a frozen LFM encoder, canonical quality/token/latency prediction, model-held-out splits, and a non-stationary replay simulator. Add LLMRouterBench and R2-Bench only after the first pipeline is trustworthy. Use a contextual bandit before considering GRPO. The research value will come from rigorous cold-start evaluation, not from adding the largest possible algorithmic stack.
