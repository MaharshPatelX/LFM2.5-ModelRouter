"""Build all six canonical tables from the pinned local xRouteBench files."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from lfm_model_router.data.adapters.xroutebench import (
    XRouteBenchAdapter,
    load_xroutebench_manifest,
    load_xroutebench_schemas,
)
from lfm_model_router.data.canonical import CANONICAL_SCHEMA_VERSION
from lfm_model_router.data.xroutebench_canonical import (
    build_xroutebench_canonical,
    write_xroutebench_canonical,
)
from lfm_model_router.storage import resolve_storage_root, validate_data_path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "data" / "manifests" / "xroutebench.json"


def build_parser() -> argparse.ArgumentParser:
    """Build the portable canonical-data command interface."""
    parser = argparse.ArgumentParser(
        description="Transform pinned xRouteBench Parquet files into canonical routing tables."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Optional storage override; defaults to the cloned repository root.",
    )
    parser.add_argument("--debug-limit", type=int, default=100)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=REPOSITORY_ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def _resolve_optional_data_path(
    value: Path | None, *, default: Path, repository_root: Path
) -> Path:
    selected = default if value is None else value
    if not selected.is_absolute():
        selected = repository_root / selected
    return validate_data_path(path=selected, repository_root=repository_root)


def main(argv: Sequence[str] | None = None) -> int:
    """Build, validate, and persist canonical xRouteBench data."""
    args = build_parser().parse_args(argv)
    if args.debug_limit < 0:
        raise ValueError("--debug-limit must be non-negative")
    storage_root = resolve_storage_root(
        repository_root=args.repository_root,
        explicit_root=args.storage_root,
    )
    manifest = load_xroutebench_manifest(args.manifest)
    schemas = load_xroutebench_schemas(args.manifest.parent / manifest.schema_snapshot)
    source_root = _resolve_optional_data_path(
        args.source_root,
        default=storage_root / "data" / "raw" / "xroutebench" / manifest.revision,
        repository_root=args.repository_root,
    )
    output_root = _resolve_optional_data_path(
        args.output_root,
        default=(
            storage_root
            / "data"
            / "processed"
            / "xroutebench"
            / manifest.revision
            / CANONICAL_SCHEMA_VERSION
        ),
        repository_root=args.repository_root,
    )
    adapter = XRouteBenchAdapter(
        data_root=source_root,
        manifest=manifest,
        schemas=schemas,
    )
    build = build_xroutebench_canonical(
        adapter=adapter,
        source_manifest_path=args.manifest,
    )
    written = write_xroutebench_canonical(
        build=build,
        output_root=output_root,
        debug_limit=args.debug_limit,
    )
    for table in sorted(written.tables, key=lambda value: value.name):
        print(f"{table.name}: {table.rows} rows, {table.size_bytes} bytes")
    print(f"canonical manifest: {written.manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
