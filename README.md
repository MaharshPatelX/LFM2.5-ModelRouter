# LFM2.5-ModelRouter

[![CI](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/actions/workflows/ci.yml/badge.svg)](https://github.com/MaharshPatelX/LFM2.5-ModelRouter/actions/workflows/ci.yml)

Research framework for routing prompts across evolving LLM portfolios with a compact Liquid AI encoder.

> **Research status:** Pre-alpha repository foundation. No benchmark results or trained router checkpoint are claimed yet.

## Research question

Can `LFM2.5-ModelRouter-350M` cold-start a completely unseen model from a small behavioral probe set and maintain a strong quality-cost-latency frontier as prices, model quality, availability, and traffic change?

## System design

The project keeps three responsibilities separate:

1. **Offline capability predictor** — estimates quality, output length, latency, failure probability, and uncertainty from a query and a candidate model profile.
2. **Runtime optimizer** — applies live prices, user preferences, availability, and hard constraints. Price-only changes require no retraining.
3. **Online adapter** — learns from selected-model feedback, handles drift, and explores newly added models within a budget.

Candidate models are scored independently. A new model is represented with metadata and a small behavioral probe profile rather than only a permanent model ID.

## Current scope

The first milestone is a reproducible data and evaluation pipeline—not a web dashboard or a multi-round RL system.

Development order:

1. Repository and reproducibility foundation.
2. xRouteBench source and license audit.
3. Canonical routing tables and leakage-safe splits.
4. Simple and learned baselines.
5. Frozen LFM query encoder and prediction heads.
6. Behavioral model profiles and held-out-model tests.
7. Non-stationary replay simulator.
8. Online bandit adapter and budget pacing.
9. External benchmarks, ablations, and research release.

See the [project blueprint](docs/PROJECT_BLUEPRINT.md) for the full ordered build plan and the [research handoff](docs/RESEARCH_HANDOFF.md) for the literature and dataset review.

## Repository layout

```text
configs/                  Versioned project and experiment settings
data/manifests/           Tracked source metadata; raw data is ignored
docs/                     Blueprint, architecture, data, and reproducibility notes
notebooks/                Exploration only; production logic belongs in src/
reports/                  Saved tables, figures, and written evaluations
scripts/                  Thin reproducible command wrappers
src/lfm_model_router/     Installable Python package
tests/                    Unit and small integration tests
```

## Development setup

Python 3.11 or 3.12 is required. Model compatibility will be verified before adding heavy ML dependencies.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m lfm_model_router --version
```

Run all foundation checks:

```bash
ruff format --check .
ruff check .
mypy src tests
pytest
python -m build
```

Equivalent Make targets are available on systems with `make`:

```bash
make check
make build
```

## Data policy

This repository does not commit downloaded benchmark data, model weights, API responses, caches, or secrets. It will commit:

- Source and license manifests.
- Schema snapshots.
- Deterministic transformation code.
- Small legally redistributable test fixtures.
- Experiment configurations and aggregate results.

Each upstream dataset and model retains its own license and usage conditions.

## Results

No results are reported yet. Results will be added only after the dataset pipeline, baselines, held-out-model evaluation, and churn simulator are reproducible.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Please do not commit private prompts, provider credentials, model weights, or downloaded benchmark contents.

## License

A code license has not yet been selected. Until a `LICENSE` file is added, default copyright applies. This does not change the separate licenses of Liquid AI models or upstream datasets.

