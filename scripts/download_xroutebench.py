"""Download and verify the pinned xRouteBench files declared by the manifest."""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from lfm_model_router.data.adapters.xroutebench import (
    XRouteBenchFile,
    XRouteBenchManifest,
    load_xroutebench_manifest,
    sha256_file,
)

DEFAULT_MANIFEST = Path("data/manifests/xroutebench.json")


def build_parser() -> argparse.ArgumentParser:
    """Build the safe-by-default download interface."""
    parser = argparse.ArgumentParser(
        description="Download pinned xRouteBench Parquet files and verify SHA-256 hashes."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Destination root; defaults to data/raw/xroutebench/<revision>.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all files. Without this flag only the smallest sample is downloaded.",
    )
    return parser


def _selected_files(
    manifest: XRouteBenchManifest, *, download_all: bool
) -> tuple[XRouteBenchFile, ...]:
    if download_all:
        return manifest.files
    return (min(manifest.files, key=lambda source_file: source_file.size_bytes),)


def _download(source_file: XRouteBenchFile, *, manifest: XRouteBenchManifest, root: Path) -> str:
    target = root / source_file.path
    target.parent.mkdir(parents=True, exist_ok=True)
    if (
        target.is_file()
        and target.stat().st_size == source_file.size_bytes
        and sha256_file(target) == source_file.sha256
    ):
        return f"verified existing {source_file.path}"

    temporary = target.with_suffix(f"{target.suffix}.part")
    request = urllib.request.Request(
        f"{manifest.resolve_base_url}{source_file.path}",
        headers={"User-Agent": "LFM2.5-ModelRouter/xRouteBench-audit"},
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=120) as response,
            temporary.open("wb") as destination,
        ):
            shutil.copyfileobj(response, destination)
        actual_size = temporary.stat().st_size
        if actual_size != source_file.size_bytes:
            raise RuntimeError(
                f"size mismatch for {source_file.path}: "
                f"expected {source_file.size_bytes}, got {actual_size}"
            )
        actual_hash = sha256_file(temporary)
        if actual_hash != source_file.sha256:
            raise RuntimeError(
                f"SHA-256 mismatch for {source_file.path}: "
                f"expected {source_file.sha256}, got {actual_hash}"
            )
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return f"downloaded and verified {source_file.path}"


def main(argv: Sequence[str] | None = None) -> int:
    """Download either the smallest sample or the complete pinned source."""
    args = build_parser().parse_args(argv)
    manifest = load_xroutebench_manifest(args.manifest)
    root = args.data_root or Path("data/raw/xroutebench") / manifest.revision
    selected = _selected_files(manifest, download_all=args.all)
    for source_file in selected:
        print(_download(source_file, manifest=manifest, root=root))
    total_bytes = sum(source_file.size_bytes for source_file in selected)
    print(f"verified {len(selected)} file(s), {total_bytes} byte(s), revision {manifest.revision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
