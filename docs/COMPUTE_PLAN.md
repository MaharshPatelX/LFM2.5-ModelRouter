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
| Part 16 release verification | Local reproduction plus optional rented Nvidia cross-check |

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
- Final release verification needs an independent Nvidia/CUDA run.

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
