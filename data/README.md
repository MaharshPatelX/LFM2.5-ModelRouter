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
