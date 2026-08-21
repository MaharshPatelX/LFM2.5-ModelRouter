# Data Workspace

Only manifests, schemas, and small legally redistributable fixtures are tracked.

Expected local directories are ignored by Git:

```text
data/raw/          Unmodified source downloads
data/interim/      Partially transformed data
data/processed/    Canonical experiment-ready tables
data/cache/        Regenerable local caches
```

Do not place credentials, private prompts, or restricted data in tracked files.

## xRouteBench

Part 2 pins xRouteBench in `data/manifests/xroutebench.json`. Download and
verify only its smallest sample with:

```bash
python scripts/download_xroutebench.py
```

Use `--all` only when all 47.38 MB of pinned Parquet files are needed. Both
modes write beneath ignored `data/raw/xroutebench/<revision>/` paths.

Because the pinned source declares no dataset license, do not move real rows
into tracked fixtures. `data/fixtures/xroutebench/` contains synthetic test
records only.
