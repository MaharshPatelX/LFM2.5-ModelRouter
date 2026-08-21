# Data Workspace

Only manifests, schemas, and small legally redistributable fixtures are tracked.

Downloads and generated data use ignored directories inside the cloned project
by default:

```text
data/raw/          Unmodified source downloads
data/interim/      Partially transformed data
data/processed/    Canonical tables, generated manifests, and data reports
data/cache/        Regenerable data caches
```

This makes the commands portable: clone the repository anywhere and run them
from its root. Set `LFM_ROUTER_STORAGE_ROOT` only when an optional external
storage location is needed; the same `data/` layout is created beneath it.

Do not place credentials, private prompts, or restricted data in tracked files.

## xRouteBench

Part 2 pins xRouteBench in `data/manifests/xroutebench.json`. Download and
verify only its smallest sample with:

```bash
python scripts/download_xroutebench.py
```

Use `--all` only when all 47.38 MB of pinned Parquet files are needed. Both
modes write beneath `data/raw/xroutebench/<revision>/` unless the optional
storage override or an explicit `--data-root` is supplied.

Because the pinned source declares no dataset license, do not move real rows
into tracked fixtures. `data/fixtures/xroutebench/` contains synthetic test
records only.

Build and validate all six Part 3 canonical tables after the full download:

```bash
python scripts/download_xroutebench.py --all
python scripts/build_xroutebench_canonical.py --debug-limit 100
```

The tables, integrity manifest and bounded debug views are written beneath
`data/processed/xroutebench/<revision>/canonical-v1/`. See
[`docs/PART3_CANONICAL_DATA.md`](../docs/PART3_CANONICAL_DATA.md) for the real
row counts and the command that feeds them into Part 4.
