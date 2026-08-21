# Contributing

LFM2.5-ModelRouter is currently a pre-alpha research project. Contributions should prioritize reproducibility, leakage prevention, and evidence over feature count.

## Set up the development environment

Use Python 3.11 or 3.12:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Before submitting a change, run:

```bash
ruff format --check .
ruff check .
mypy src tests
pytest
python -m build
```

## Contribution rules

- Keep dataset-specific behavior inside source adapters.
- Preserve raw scores and token counts before normalization.
- Add tests for data validation, price calculations, and split leakage.
- Pin source revisions in manifests instead of relying on mutable defaults.
- Keep live prices outside learned model weights.
- Do not expose hidden counterfactual outcomes to online policies.
- Store reusable logic in `src/`, not notebooks.
- Report unsuccessful experiments when they affect research conclusions.

## Data, credentials, and generated files

Never commit:

- API keys or `.env` files.
- Private prompts or user data.
- Downloaded benchmark contents unless redistribution is explicitly allowed.
- Model weights or checkpoints.
- Local caches and experiment service metadata.

## Pull requests

Keep each pull request focused. Include:

- What changed and why.
- The checks that were run.
- Dataset/model revisions affected.
- Any license, leakage, or reproducibility considerations.
