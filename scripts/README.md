# Scripts

Scripts remain thin command wrappers around reusable package code. Planned
commands include canonical table construction, offline training, profile
creation, static evaluation, and churn simulation.

`download_xroutebench.py` downloads and verifies the smallest pinned
xRouteBench sample by default. Pass `--all` to download all manifest files.
By default, real data is written beneath the cloned project's ignored
`data/raw/` directory. `LFM_ROUTER_STORAGE_ROOT` remains an optional override
for larger external storage.

`build_leakage_safe_splits.py` consumes the query-table and model-registry
Parquet files produced by Part 3; bounded JSONL debug views are also supported.
It writes versioned split manifests, a common deduplication manifest, and the
audit report beneath `data/processed/part4/`. When timestamps do not exist,
`--allow-unsupported-temporal` records that limitation instead of inventing
dates. Moving the repository does not require configuration changes.

`build_xroutebench_canonical.py` reads the verified files in `data/raw/`,
validates every query/outcome relationship, and writes all six canonical
Parquet tables plus bounded JSONL debug views beneath `data/processed/`.
