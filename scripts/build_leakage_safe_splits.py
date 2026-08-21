"""Build the six Part 4 split manifests from Part 3 JSONL debug exports."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from lfm_model_router.data.deduplication import deduplicate_queries
from lfm_model_router.data.split_io import (
    load_part4_config,
    load_split_models,
    load_split_queries,
    write_split_bundle,
)
from lfm_model_router.data.splits import (
    SPLIT_STRATEGIES,
    SplitError,
    SplitManifest,
    SplitStrategy,
    build_split_manifest,
)
from lfm_model_router.storage import (
    resolve_storage_root,
    validate_data_path,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPOSITORY_ROOT / "configs" / "splits" / "xroutebench_v1.toml"


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit Part 3-to-Part 4 command interface."""
    parser = argparse.ArgumentParser(
        description="Create deterministic deduplication and leakage-safe split artifacts."
    )
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--canonical-schema-version", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="External output root; defaults to the configured environment variable.",
    )
    parser.add_argument(
        "--allow-unsupported-temporal",
        action="store_true",
        help="Write an explicit unsupported artifact when trustworthy dates are absent.",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=REPOSITORY_ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def _require_data_input(*, path: Path, repository_root: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (repository_root / path).resolve()
    if not resolved.is_file():
        raise ValueError(f"input file does not exist: {resolved}")
    validate_data_path(
        path=resolved,
        repository_root=repository_root,
    )
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    """Deduplicate Part 3 exports and write all strategies to portable data storage."""
    args = build_parser().parse_args(argv)
    part4_config = load_part4_config(args.config)
    storage_root = resolve_storage_root(
        repository_root=args.repository_root,
        explicit_root=args.storage_root,
        variable=part4_config.storage_environment_variable,
    )
    query_path = _require_data_input(
        path=args.queries,
        repository_root=args.repository_root,
    )
    model_path = _require_data_input(
        path=args.models,
        repository_root=args.repository_root,
    )

    queries = load_split_queries(query_path)
    models = load_split_models(model_path)
    deduplication = deduplicate_queries(
        queries,
        config=part4_config.deduplication,
    )
    split_config = part4_config.split_build_config(
        dataset_id=args.dataset_id,
        dataset_revision=args.dataset_revision,
        canonical_schema_version=args.canonical_schema_version,
    )
    manifests: dict[SplitStrategy, SplitManifest] = {}
    unsupported: dict[SplitStrategy, str] = {}
    for strategy in SPLIT_STRATEGIES:
        try:
            manifests[strategy] = build_split_manifest(
                strategy,
                queries=queries,
                models=models,
                deduplication=deduplication,
                config=split_config,
            )
        except SplitError as error:
            if (
                strategy != "temporal"
                or not args.allow_unsupported_temporal
                or "requires" not in str(error).casefold()
            ):
                raise
            unsupported[strategy] = str(error)
    paths = write_split_bundle(
        storage_root=storage_root,
        repository_root=args.repository_root,
        config=split_config,
        deduplication=deduplication,
        manifests=manifests,
        unsupported=unsupported,
    )
    print(f"wrote {len(paths.split_manifests)} split manifests to {paths.manifest_directory}")
    if paths.unsupported_manifests:
        print(f"wrote {len(paths.unsupported_manifests)} explicit unsupported-strategy artifact(s)")
    print(f"wrote deduplication report to {paths.deduplication_report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
