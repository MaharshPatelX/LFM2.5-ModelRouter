# Dataset Manifests

This tracked directory holds compact source revisions, file metadata, schema
snapshots, checksums, and license notes. Generated split manifests can contain
large ID lists, so they belong beneath the ignored
`data/processed/part4/manifests/splits/` directory.

- `xroutebench.json` pins the immutable source revision and all 41 files.
- `xroutebench_schema.json` records all 17 config schemas, split row counts,
  and non-zero null counts.

The human-readable evidence and decisions are in
[`reports/xroutebench_audit.md`](../../reports/xroutebench_audit.md).
