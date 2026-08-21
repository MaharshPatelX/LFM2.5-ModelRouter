# Local Compute Plan

## Active decision

The current project trains and evaluates **only**
`LFM2.5-ModelRouter-350M`. Larger LFM variants are not part of the active MVP
or its compute budget. They may be reconsidered only after the 350M research
release is complete.

| Resource | Current plan |
|---|---|
| Query encoder scale | 350M parameters only |
| Encoder candidate | `LiquidAI/LFM2.5-Embedding-350M`; pin the exact revision in Part 6 |
| Primary accelerator | Local AMD Radeon RX 7900 XTX with 24 GB VRAM |
| Host memory | Existing 16 GB RAM |
| Cloud GPU | Fallback only; not the default training environment |
| Default training mode | Frozen encoder with cached query embeddings |
| Fine-tuning | Partial/full fine-tuning only as a later controlled ablation |

There is no RAM-upgrade requirement before development or training begins.
The project will measure the real workload before recommending any hardware
purchase.

## Why this is practical

The current canonical xRouteBench build contains 15,339 eligible queries and
231,750 query/model outcomes. The 350M encoder processes each unique query
once, and the resulting embedding is referenced by outcome rows rather than
copied 18 times.

This design keeps both GPU and system-memory use bounded:

- Read Parquet in batches and select only required columns.
- Cache one embedding per stable query ID.
- Store outcome-to-query indices instead of repeated embedding tensors.
- Begin with zero or one data-loader worker.
- Use small GPU batches plus gradient accumulation when required.
- Keep only the current and best checkpoint.
- Avoid CPU or disk offloading unless a measured run requires it.

## Execution by project stage

| Project stage | Default compute |
|---|---|
| Part 5 baselines | Local CPU; GPU optional for small learned baselines |
| Part 6 embedding cache | Local RX 7900 XTX |
| Parts 7–11 model training and evaluation | Local RX 7900 XTX |
| Parts 12–13 replay and online policies | CPU first; local GPU only for neural components |
| Parts 14–15 external tests and ablations | Local GPU in queued, resumable runs |
| Part 16 release verification | Local reproduction plus optional rented NVIDIA cross-check |

## Staged engineering workflow

GPU-dependent work has three separate states. They must not be treated as the
same thing:

| State | Meaning | Evidence |
|---|---|---|
| Implementation ready | Interfaces and code exist and pass CPU tests on tiny deterministic data | Unit tests, type checks and a CPU smoke command |
| Hardware validated | The same code completes bounded forward and backward work on the RX 7900 XTX | Recorded device, software revisions, memory, throughput and 100-step result |
| Experiment complete | The real configuration finishes on the intended split and saves reproducible artifacts | Resolved config, checkpoint, metrics, hashes and run report |

A GPU-dependent project part cannot be marked **Done** from CPU tests alone.
CPU tests let development continue before the GPU arrives; the hardware and
experiment gates still have to pass later.

## What can be implemented before GPU validation

| Part | Safe work before the GPU arrives | Work that still requires real validation |
|---:|---|---|
| 5 | Complete all baseline policies, metrics and CPU tests | Optional acceleration only |
| 6 | Encoder interface, device configuration, cache format and CPU smoke test | ROCm loading, VRAM, throughput and backward pass |
| 7 | Profile schemas, encoders and tests with synthetic embeddings | Neural-profile training at real scale |
| 8 | Prediction heads, losses, masking, trainer and tiny-data tests | Full training, calibration and tuning |
| 9 | Complete registry, constraints, price logic and optimizer on CPU | Performance check with real predictions |
| 10 | Evaluation metrics, artifact writers and figure code | Reports from trained checkpoints |
| 11 | Cold-start protocol and leakage assertions | Held-out-model training runs |
| 12 | Complete deterministic replay simulator on CPU | Scale and performance checks |
| 13 | Bandit interfaces, budget controller and synthetic replay tests | Neural-policy and long replay experiments |
| 14 | Adapter contracts after each source/license audit | Real external evaluation |
| 15 | Ablation scheduler, seed handling and statistics code | Multi-seed experiment campaign |
| 16 | Release templates and reproducibility command | Final claims, figures, model card and weights |

This table authorizes scaffolding and bounded tests, not one giant unvalidated
implementation. Later interfaces should be built only after the earlier
contract they consume has stabilized.

## Validation ladder

Every learned component advances through the same sequence:

1. Validate configuration and schemas without loading a model.
2. Run deterministic unit tests using tiny fixtures or synthetic embeddings.
3. Run one CPU forward pass.
4. Run one training batch and verify finite losses and gradients.
5. Run the RX 7900 XTX hardware acceptance test.
6. Run 100 optimizer steps and verify memory remains bounded.
7. Run one complete epoch with checkpoint/resume enabled.
8. Run the full configuration, then multi-seed and ablation jobs.

A failure returns to the smallest stage that reproduces it. Expensive runs do
not begin while a cheaper stage is failing.

## Device-neutral code rules

- Select `auto`, `cpu` or `cuda` through configuration; do not scatter device
  checks throughout model code.
- Do not hard-code NVIDIA-only package imports in shared modules.
- Keep dtype and mixed-precision policy in one runtime configuration.
- Make CPU fixtures small enough for normal CI.
- Use fake embeddings to test downstream model logic without loading LFM.
- Save optimizer, scheduler, scaler, seed and data position for resumable runs.
- Log the physical GPU name, driver, ROCm, PyTorch and model revisions.
- Keep correctness tests separate from throughput benchmarks.

## Immediate pre-GPU sequence

The GPU arrival does not justify building Parts 5–16 in one untested change.
The immediate order is:

1. Complete Part 5 end to end on CPU.
2. Define Part 6's encoder interface, revision-aware cache and device contract.
3. Add CPU fixtures and the bounded hardware-acceptance command.
4. Validate the interface on the RX 7900 XTX when it is installed.
5. Continue to Part 7 only after the Part 6 contract and artifacts are stable.

## Hardware acceptance gate

When the RX 7900 XTX is installed, Part 6 must first run a bounded acceptance
test:

1. Create a separate, pinned Python/ROCm environment.
2. Verify that PyTorch detects the expected GPU and 24 GB VRAM.
3. Load the 350M encoder and encode a small fixture.
4. Benchmark 1,000 real canonical queries.
5. Run 100 optimizer steps with backward propagation.
6. Record peak VRAM, peak host RAM, throughput, temperature and failures.
7. Extrapolate measured runtime before scheduling a full run.

The initial Windows route must follow AMD's current
[PyTorch compatibility matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html).
If a required training operation is unsupported, native Linux is the next
local option.

## Host-memory rule

The existing 16 GB of RAM is accepted for Parts 5–6 and remains the default
for later work unless measurements show a real problem. An upgrade is
considered only after reproducible out-of-memory failures or sustained paging
under the bounded loader design.

## Cloud fallback rule

A rented GPU is allowed only when one of these conditions is recorded:

- A required operation is unsupported by the validated local ROCm stack.
- A deadline makes a long multi-seed queue impractical on one local GPU.
- Final release verification needs an independent NVIDIA/CUDA run.

Every cloud run must use the same repository command and saved configuration
as the local run. Checkpoints and aggregate results are copied back before the
instance and unused storage are deleted.

## Planning estimates

These are budgeting ranges, not claimed benchmark results:

| Work unit | Initial estimate |
|---|---:|
| Full embedding-cache build | 5–30 minutes |
| One frozen-encoder router run | 20–60 minutes |
| One LoRA experiment | 1–3 GPU-hours |
| One full 350M fine-tuning experiment | 1–4 GPU-hours |
| MVP experimentation through Part 10 | 20–50 GPU-hours |
| Research campaign through Part 15 | 120–300 GPU-hours |

The acceptance benchmark replaces these ranges with measured estimates before
we commit to the expensive experiment stages.
