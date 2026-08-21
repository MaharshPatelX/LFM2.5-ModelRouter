"""Typed loading for small, dependency-free project configurations."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Repository-wide settings needed before dataset-specific configuration."""

    name: str
    seed: int
    data_dir: Path
    artifacts_dir: Path
    reports_dir: Path


def _require_mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a TOML table")
    return value


def _require_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_seed(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("project.seed must be a non-negative integer")
    return value


def load_project_config(path: Path) -> ProjectConfig:
    """Load and validate a project TOML file."""
    with path.open("rb") as config_file:
        raw = tomllib.load(config_file)

    project = _require_mapping(raw.get("project"), field="project")
    paths = _require_mapping(raw.get("paths"), field="paths")

    return ProjectConfig(
        name=_require_string(project.get("name"), field="project.name"),
        seed=_require_seed(project.get("seed")),
        data_dir=Path(_require_string(paths.get("data_dir"), field="paths.data_dir")),
        artifacts_dir=Path(
            _require_string(paths.get("artifacts_dir"), field="paths.artifacts_dir")
        ),
        reports_dir=Path(_require_string(paths.get("reports_dir"), field="paths.reports_dir")),
    )
