"""Portable resolution of repository-local or optional external data storage."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

STORAGE_ROOT_ENV = "LFM_ROUTER_STORAGE_ROOT"


class StorageConfigurationError(ValueError):
    """Raised when a project storage path is missing or unsafe."""


def storage_root_from_environment(
    *,
    variable: str = STORAGE_ROOT_ENV,
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Return the absolute external storage root declared by an environment variable."""
    values = os.environ if environment is None else environment
    raw_value = values.get(variable)
    if raw_value is None or not raw_value.strip():
        raise StorageConfigurationError(
            f"{variable} is not set; point it to an external storage directory"
        )
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        raise StorageConfigurationError(f"{variable} must contain an absolute path: {path}")
    return path.resolve()


def resolve_storage_root(
    *,
    repository_root: Path,
    explicit_root: Path | None = None,
    variable: str = STORAGE_ROOT_ENV,
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Use an explicit root, an environment override, or the repository by default."""
    if explicit_root is not None:
        selected = explicit_root
    else:
        values = os.environ if environment is None else environment
        configured = values.get(variable)
        selected = Path(configured).expanduser() if configured else repository_root
    return validate_storage_root(storage_root=selected, repository_root=repository_root)


def validate_storage_root(*, storage_root: Path, repository_root: Path) -> Path:
    """Allow the repository root or an external root, but reject nested code paths."""
    if not storage_root.is_absolute():
        raise StorageConfigurationError(f"storage root must be absolute: {storage_root}")

    root = storage_root.resolve()
    repository = repository_root.resolve()
    if root != repository and repository in root.parents:
        raise StorageConfigurationError(
            f"storage root must be the repository root or a directory outside it: {root}"
        )
    return root


def validate_data_path(*, path: Path, repository_root: Path) -> Path:
    """Allow external paths or paths beneath the repository's ignored data directory."""
    if not path.is_absolute():
        raise StorageConfigurationError(f"data path must be absolute: {path}")
    resolved = path.resolve()
    repository = repository_root.resolve()
    local_data = (repository / "data").resolve()
    inside_repository = resolved == repository or repository in resolved.parents
    inside_local_data = resolved == local_data or local_data in resolved.parents
    if inside_repository and not inside_local_data:
        raise StorageConfigurationError(
            f"repository-local data must stay beneath {local_data}: {resolved}"
        )
    return resolved
