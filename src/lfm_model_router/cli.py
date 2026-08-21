"""Command-line entry point for repository smoke checks."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from lfm_model_router import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the project command-line parser."""
    parser = argparse.ArgumentParser(
        prog="lfm-model-router",
        description="Research tooling for adaptive LLM model routing.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
