"""Value-preserving access to the pinned xRouteBench source files."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast


class XRouteBenchError(ValueError):
    """Raised when xRouteBench metadata or source data fails validation."""


class XRouteBenchDependencyError(RuntimeError):
    """Raised when the optional Parquet dependency is unavailable."""


@dataclass(frozen=True, slots=True)
class XRouteBenchFile:
    """One immutable Parquet file declared by the source manifest."""

    config: str
    split: str
    path: str
    rows: int
    columns: int
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class XRouteBenchField:
    """One source field exactly as observed in the pinned dataset."""

    name: str
    type: str


@dataclass(frozen=True, slots=True)
class XRouteBenchManifest:
    """Validated subset of the machine-readable xRouteBench manifest."""

    dataset_id: str
    revision: str
    schema_snapshot: str
    resolve_base_url: str
    files: tuple[XRouteBenchFile, ...]

    def file_for(self, config: str, split: str) -> XRouteBenchFile:
        """Return one source file, rejecting unknown config/split pairs."""
        for source_file in self.files:
            if source_file.config == config and source_file.split == split:
                return source_file
        raise XRouteBenchError(f"unknown xRouteBench config/split: {config}/{split}")


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise XRouteBenchError(f"{field} must be a JSON object")
    return cast(dict[str, object], value)


def _list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise XRouteBenchError(f"{field} must be a JSON array")
    return cast(list[object], value)


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise XRouteBenchError(f"{field} must be a non-empty string")
    return value


def _integer(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise XRouteBenchError(f"{field} must be a non-negative integer")
    return value


def _read_json(path: Path) -> object:
    try:
        with path.open(encoding="utf-8") as source:
            return cast(object, json.load(source))
    except (OSError, json.JSONDecodeError) as error:
        raise XRouteBenchError(f"could not read JSON metadata at {path}: {error}") from error


def _validate_relative_path(value: str, *, field: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise XRouteBenchError(f"{field} must remain inside the data root")
    return value


def load_xroutebench_manifest(path: Path) -> XRouteBenchManifest:
    """Load and validate the tracked xRouteBench source manifest."""
    raw = _mapping(_read_json(path), field="manifest")
    source_urls = _mapping(raw.get("source_urls"), field="manifest.source_urls")
    file_values = _list(raw.get("files"), field="manifest.files")

    files: list[XRouteBenchFile] = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, value in enumerate(file_values):
        item = _mapping(value, field=f"manifest.files[{index}]")
        config = _string(item.get("config"), field=f"manifest.files[{index}].config")
        split = _string(item.get("split"), field=f"manifest.files[{index}].split")
        pair = (config, split)
        if pair in seen_pairs:
            raise XRouteBenchError(f"duplicate manifest config/split: {config}/{split}")
        seen_pairs.add(pair)
        files.append(
            XRouteBenchFile(
                config=config,
                split=split,
                path=_validate_relative_path(
                    _string(item.get("path"), field=f"manifest.files[{index}].path"),
                    field=f"manifest.files[{index}].path",
                ),
                rows=_integer(item.get("rows"), field=f"manifest.files[{index}].rows"),
                columns=_integer(item.get("columns"), field=f"manifest.files[{index}].columns"),
                size_bytes=_integer(
                    item.get("size_bytes"), field=f"manifest.files[{index}].size_bytes"
                ),
                sha256=_string(item.get("sha256"), field=f"manifest.files[{index}].sha256"),
            )
        )

    if not files:
        raise XRouteBenchError("manifest.files must not be empty")

    return XRouteBenchManifest(
        dataset_id=_string(raw.get("dataset_id"), field="manifest.dataset_id"),
        revision=_string(raw.get("revision"), field="manifest.revision"),
        schema_snapshot=_validate_relative_path(
            _string(raw.get("schema_snapshot"), field="manifest.schema_snapshot"),
            field="manifest.schema_snapshot",
        ),
        resolve_base_url=_string(
            source_urls.get("resolve_base"), field="manifest.source_urls.resolve_base"
        ),
        files=tuple(files),
    )


def load_xroutebench_schemas(path: Path) -> dict[str, tuple[XRouteBenchField, ...]]:
    """Load exact per-config field names and source dtypes."""
    raw = _mapping(_read_json(path), field="schema")
    configs = _list(raw.get("configs"), field="schema.configs")
    result: dict[str, tuple[XRouteBenchField, ...]] = {}

    for config_index, config_value in enumerate(configs):
        config = _mapping(config_value, field=f"schema.configs[{config_index}]")
        name = _string(config.get("name"), field=f"schema.configs[{config_index}].name")
        if name in result:
            raise XRouteBenchError(f"duplicate schema config: {name}")
        field_values = _list(config.get("fields"), field=f"schema.configs[{config_index}].fields")
        fields: list[XRouteBenchField] = []
        field_names: set[str] = set()
        for field_index, field_value in enumerate(field_values):
            source_field = _mapping(
                field_value,
                field=f"schema.configs[{config_index}].fields[{field_index}]",
            )
            field_name = _string(
                source_field.get("name"),
                field=f"schema.configs[{config_index}].fields[{field_index}].name",
            )
            if field_name in field_names:
                raise XRouteBenchError(f"duplicate field {field_name!r} in schema {name}")
            field_names.add(field_name)
            fields.append(
                XRouteBenchField(
                    name=field_name,
                    type=_string(
                        source_field.get("type"),
                        field=f"schema.configs[{config_index}].fields[{field_index}].type",
                    ),
                )
            )
        result[name] = tuple(fields)

    return result


def sha256_file(path: Path) -> str:
    """Return a file SHA-256 without loading the complete file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl_records(path: Path) -> tuple[dict[str, object], ...]:
    """Load a small JSONL fixture without renaming, coercing, or filling values."""
    records: list[dict[str, object]] = []
    try:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    raise XRouteBenchError(f"blank JSONL record at {path}:{line_number}")
                value = cast(object, json.loads(line))
                record = _mapping(value, field=f"{path}:{line_number}")
                records.append(dict(record))
    except (OSError, json.JSONDecodeError) as error:
        raise XRouteBenchError(f"could not read JSONL records at {path}: {error}") from error
    return tuple(records)


def _normalise_arrow_type(value: str) -> str:
    aliases = {"double": "float64", "large_string": "string"}
    if value in aliases:
        return aliases[value]
    if value.startswith("list<") and "string" in value:
        return "list[string]"
    return value


class XRouteBenchAdapter:
    """Read pinned xRouteBench Parquet files without source-field transformations."""

    def __init__(
        self,
        *,
        data_root: Path,
        manifest: XRouteBenchManifest,
        schemas: Mapping[str, tuple[XRouteBenchField, ...]],
    ) -> None:
        self.data_root = data_root
        self.manifest = manifest
        self.schemas = dict(schemas)

    @classmethod
    def from_manifest(cls, *, data_root: Path, manifest_path: Path) -> XRouteBenchAdapter:
        """Construct an adapter from the tracked manifest and its schema snapshot."""
        manifest = load_xroutebench_manifest(manifest_path)
        schema_path = manifest_path.parent / manifest.schema_snapshot
        return cls(
            data_root=data_root,
            manifest=manifest,
            schemas=load_xroutebench_schemas(schema_path),
        )

    def local_path(self, config: str, split: str) -> Path:
        """Resolve a manifest path while preventing escape from the local data root."""
        source_file = self.manifest.file_for(config, split)
        root = self.data_root.resolve()
        candidate = (root / source_file.path).resolve()
        if candidate != root and root not in candidate.parents:
            raise XRouteBenchError(f"source path escapes data root: {source_file.path}")
        return candidate

    def verify_file(self, config: str, split: str) -> Path:
        """Verify existence, byte size, and SHA-256 for one local source file."""
        source_file = self.manifest.file_for(config, split)
        path = self.local_path(config, split)
        if not path.is_file():
            raise XRouteBenchError(f"xRouteBench source file is missing: {path}")
        actual_size = path.stat().st_size
        if actual_size != source_file.size_bytes:
            raise XRouteBenchError(
                f"size mismatch for {path}: expected {source_file.size_bytes}, got {actual_size}"
            )
        actual_hash = sha256_file(path)
        if actual_hash != source_file.sha256:
            raise XRouteBenchError(
                f"SHA-256 mismatch for {path}: expected {source_file.sha256}, got {actual_hash}"
            )
        return path

    def iter_split(
        self,
        config: str,
        split: str,
        *,
        batch_size: int = 1024,
        verify_integrity: bool = True,
    ) -> Iterator[dict[str, object]]:
        """Yield source records unchanged, validating schema and final row count."""
        if batch_size <= 0:
            raise XRouteBenchError("batch_size must be positive")
        source_file = self.manifest.file_for(config, split)
        path = (
            self.verify_file(config, split) if verify_integrity else self.local_path(config, split)
        )
        if not path.is_file():
            raise XRouteBenchError(f"xRouteBench source file is missing: {path}")
        expected_fields = self.schemas.get(config)
        if expected_fields is None:
            raise XRouteBenchError(f"schema is missing for xRouteBench config: {config}")

        try:
            parquet = importlib.import_module("pyarrow.parquet")
        except ModuleNotFoundError as error:
            raise XRouteBenchDependencyError(
                'Parquet ingestion requires the data extra: pip install -e ".[data]"'
            ) from error

        parquet_file = parquet.ParquetFile(path)
        arrow_schema = parquet_file.schema_arrow
        actual_names = tuple(arrow_schema.names)
        expected_names = tuple(field.name for field in expected_fields)
        if actual_names != expected_names:
            raise XRouteBenchError(
                f"column mismatch for {config}: expected {expected_names}, got {actual_names}"
            )
        actual_types = tuple(_normalise_arrow_type(str(field.type)) for field in arrow_schema)
        expected_types = tuple(field.type for field in expected_fields)
        if actual_types != expected_types:
            raise XRouteBenchError(
                f"dtype mismatch for {config}: expected {expected_types}, got {actual_types}"
            )

        rows_seen = 0
        for batch in parquet_file.iter_batches(batch_size=batch_size):
            for raw_record in batch.to_pylist():
                record = cast(dict[str, object], raw_record)
                rows_seen += 1
                yield dict(record)
        if rows_seen != source_file.rows:
            raise XRouteBenchError(
                f"row-count mismatch for {config}/{split}: "
                f"expected {source_file.rows}, got {rows_seen}"
            )
