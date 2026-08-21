"""Configuration, JSONL exchange, and portable artifact I/O for Part 4."""

from __future__ import annotations

import importlib
import json
import re
import tomllib
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from lfm_model_router.data.deduplication import (
    DeduplicationConfig,
    DeduplicationResult,
    QueryForSplitting,
)
from lfm_model_router.data.splits import (
    SPLIT_STRATEGIES,
    ModelForSplitting,
    SplitBuildConfig,
    SplitManifest,
    SplitRatios,
    SplitStrategy,
    deduplication_digest,
)
from lfm_model_router.storage import validate_storage_root


class SplitIOError(ValueError):
    """Raised when Part 4 configuration or exchange files are invalid."""


@dataclass(frozen=True, slots=True)
class Part4Config:
    """Static split and deduplication settings loaded from TOML."""

    seed: int
    ratios: SplitRatios
    deduplication: DeduplicationConfig
    manifest_version: str
    algorithm_version: str
    storage_environment_variable: str
    use_project_root_by_default: bool

    def split_build_config(
        self,
        *,
        dataset_id: str,
        dataset_revision: str,
        canonical_schema_version: str,
    ) -> SplitBuildConfig:
        """Bind static settings to one canonical dataset revision."""
        return SplitBuildConfig(
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
            canonical_schema_version=canonical_schema_version,
            seed=self.seed,
            ratios=self.ratios,
            manifest_version=self.manifest_version,
            algorithm_version=self.algorithm_version,
        )


@dataclass(frozen=True, slots=True)
class SplitBundlePaths:
    """External locations written for one complete Part 4 bundle."""

    manifest_directory: Path
    deduplication_manifest: Path
    split_manifests: tuple[Path, ...]
    unsupported_manifests: tuple[Path, ...]
    deduplication_report: Path


def _mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SplitIOError(f"{field} must be a table or JSON object")
    return cast(dict[str, Any], value)


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SplitIOError(f"{field} must be a non-empty string")
    return value


def _integer(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SplitIOError(f"{field} must be an integer")
    return value


def _number(value: object, *, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SplitIOError(f"{field} must be a number")
    return float(value)


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise SplitIOError(f"{field} must be a boolean")
    return value


def load_part4_config(path: Path) -> Part4Config:
    """Load the versioned Part 4 TOML configuration."""
    try:
        with path.open("rb") as source:
            raw = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SplitIOError(f"could not read Part 4 configuration at {path}: {error}") from error

    manifest = _mapping(raw.get("manifest"), field="manifest")
    split = _mapping(raw.get("split"), field="split")
    deduplication = _mapping(raw.get("deduplication"), field="deduplication")
    storage = _mapping(raw.get("storage"), field="storage")
    config = Part4Config(
        seed=_integer(split.get("seed"), field="split.seed"),
        ratios=SplitRatios(
            train=_number(split.get("train_ratio"), field="split.train_ratio"),
            validation=_number(split.get("validation_ratio"), field="split.validation_ratio"),
            test=_number(split.get("test_ratio"), field="split.test_ratio"),
        ),
        deduplication=DeduplicationConfig(
            normalization_version=_string(
                deduplication.get("normalization_version"),
                field="deduplication.normalization_version",
            ),
            near_duplicate_threshold=_number(
                deduplication.get("near_duplicate_threshold"),
                field="deduplication.near_duplicate_threshold",
            ),
            shingle_size=_integer(
                deduplication.get("shingle_size"), field="deduplication.shingle_size"
            ),
            signature_size=_integer(
                deduplication.get("signature_size"), field="deduplication.signature_size"
            ),
            max_bucket_size=_integer(
                deduplication.get("max_bucket_size"), field="deduplication.max_bucket_size"
            ),
            max_candidate_pairs=_integer(
                deduplication.get("max_candidate_pairs"),
                field="deduplication.max_candidate_pairs",
            ),
        ),
        manifest_version=_string(manifest.get("version"), field="manifest.version"),
        algorithm_version=_string(
            manifest.get("algorithm_version"), field="manifest.algorithm_version"
        ),
        storage_environment_variable=_string(
            storage.get("root_environment_variable"),
            field="storage.root_environment_variable",
        ),
        use_project_root_by_default=_boolean(
            storage.get("use_project_root_by_default"),
            field="storage.use_project_root_by_default",
        ),
    )
    if config.seed < 0:
        raise SplitIOError("split.seed must be non-negative")
    config.ratios.validate()
    config.deduplication.validate()
    if not config.use_project_root_by_default:
        raise SplitIOError("storage.use_project_root_by_default must remain true")
    return config


def _optional_string(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _string(value, field=field)


def _datetime(value: object, *, field: str) -> datetime | None:
    raw_value = _optional_string(value, field=field)
    if raw_value is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SplitIOError(f"{field} must be an ISO-8601 timestamp: {raw_value}") from error
    if parsed.tzinfo is None:
        raise SplitIOError(f"{field} must include a timezone: {raw_value}")
    return parsed


def _string_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SplitIOError(f"{field} must be a JSON array")
    return tuple(_string(item, field=f"{field}[]") for item in cast(list[object], value))


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    raise SplitIOError(f"blank JSONL record at {path}:{line_number}")
                rows.append(_mapping(json.loads(line), field=f"{path}:{line_number}"))
    except (OSError, json.JSONDecodeError) as error:
        raise SplitIOError(f"could not read JSONL at {path}: {error}") from error
    if not rows:
        raise SplitIOError(f"JSONL file contains no records: {path}")
    return tuple(rows)


def load_split_queries_jsonl(path: Path) -> tuple[QueryForSplitting, ...]:
    """Load the canonical-query fields consumed by Part 4."""
    queries: list[QueryForSplitting] = []
    for index, row in enumerate(_read_jsonl(path)):
        if row.get("has_outcomes") is False:
            continue
        prefix = f"queries[{index}]"
        is_probe_value = row.get("is_probe", False)
        source_value = row.get("source")
        if source_value is None:
            source_value = (
                f"{row.get('source_dataset')}:{row.get('source_config')}"
                if row.get("source_dataset") and row.get("source_config")
                else None
            )
        queries.append(
            QueryForSplitting(
                query_id=_string(row.get("query_id"), field=f"{prefix}.query_id"),
                prompt=_string(row.get("prompt"), field=f"{prefix}.prompt"),
                task=_string(row.get("task"), field=f"{prefix}.task"),
                source=_string(source_value, field=f"{prefix}.source"),
                source_query_id=_optional_string(
                    row.get("source_query_id"), field=f"{prefix}.source_query_id"
                ),
                lineage_id=_optional_string(row.get("lineage_id"), field=f"{prefix}.lineage_id"),
                observed_at=_datetime(row.get("observed_at"), field=f"{prefix}.observed_at"),
                is_probe=_boolean(is_probe_value, field=f"{prefix}.is_probe"),
            )
        )
    return tuple(queries)


def load_split_models_jsonl(path: Path) -> tuple[ModelForSplitting, ...]:
    """Load the canonical model-registry fields consumed by Part 4."""
    models: list[ModelForSplitting] = []
    for index, row in enumerate(_read_jsonl(path)):
        prefix = f"models[{index}]"
        models.append(
            ModelForSplitting(
                model_id=_string(row.get("model_id"), field=f"{prefix}.model_id"),
                provider=_string(row.get("provider"), field=f"{prefix}.provider"),
                family=_string(row.get("family"), field=f"{prefix}.family"),
                version=_string(row.get("version"), field=f"{prefix}.version"),
                aliases=_string_tuple(row.get("aliases"), field=f"{prefix}.aliases"),
                available_at=_datetime(row.get("available_at"), field=f"{prefix}.available_at"),
            )
        )
    return tuple(models)


def _read_parquet(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        parquet = importlib.import_module("pyarrow.parquet")
    except ModuleNotFoundError as error:
        raise SplitIOError('Parquet input requires: pip install -e ".[data]"') from error
    try:
        rows = parquet.read_table(path).to_pylist()
    except OSError as error:
        raise SplitIOError(f"could not read Parquet at {path}: {error}") from error
    return tuple(cast(dict[str, Any], row) for row in rows)


def load_split_queries_parquet(path: Path) -> tuple[QueryForSplitting, ...]:
    """Load eligible queries directly from the Part 3 canonical Parquet table."""
    queries: list[QueryForSplitting] = []
    for index, row in enumerate(_read_parquet(path)):
        if row.get("has_outcomes") is not True:
            continue
        prefix = f"queries[{index}]"
        source = f"{_string(row.get('source_dataset'), field=f'{prefix}.source_dataset')}:"
        source += _string(row.get("source_config"), field=f"{prefix}.source_config")
        queries.append(
            QueryForSplitting(
                query_id=_string(row.get("query_id"), field=f"{prefix}.query_id"),
                prompt=_string(row.get("prompt"), field=f"{prefix}.prompt"),
                task=_string(row.get("task"), field=f"{prefix}.task"),
                source=source,
                source_query_id=_optional_string(
                    row.get("source_query_id"), field=f"{prefix}.source_query_id"
                ),
                observed_at=cast(datetime | None, row.get("observed_at")),
                is_probe=_boolean(row.get("is_probe"), field=f"{prefix}.is_probe"),
            )
        )
    if not queries:
        raise SplitIOError(f"canonical query table has no rows with outcomes: {path}")
    return tuple(queries)


def load_split_models_parquet(path: Path) -> tuple[ModelForSplitting, ...]:
    """Load canonical model identities directly from Part 3 Parquet."""
    models: list[ModelForSplitting] = []
    for index, row in enumerate(_read_parquet(path)):
        prefix = f"models[{index}]"
        aliases = row.get("aliases")
        if not isinstance(aliases, list):
            raise SplitIOError(f"{prefix}.aliases must be a list")
        models.append(
            ModelForSplitting(
                model_id=_string(row.get("model_id"), field=f"{prefix}.model_id"),
                provider=_string(row.get("provider"), field=f"{prefix}.provider"),
                family=_string(row.get("family"), field=f"{prefix}.family"),
                version=_string(row.get("version"), field=f"{prefix}.version"),
                aliases=tuple(_string(alias, field=f"{prefix}.aliases[]") for alias in aliases),
                available_at=cast(datetime | None, row.get("available_at")),
            )
        )
    if not models:
        raise SplitIOError(f"canonical model table contains no rows: {path}")
    return tuple(models)


def load_split_queries(path: Path) -> tuple[QueryForSplitting, ...]:
    """Load split queries from canonical Parquet or JSONL debug exchange."""
    if path.suffix.casefold() == ".parquet":
        return load_split_queries_parquet(path)
    if path.suffix.casefold() == ".jsonl":
        return load_split_queries_jsonl(path)
    raise SplitIOError(f"query input must be .parquet or .jsonl: {path}")


def load_split_models(path: Path) -> tuple[ModelForSplitting, ...]:
    """Load split models from canonical Parquet or JSONL debug exchange."""
    if path.suffix.casefold() == ".parquet":
        return load_split_models_parquet(path)
    if path.suffix.casefold() == ".jsonl":
        return load_split_models_jsonl(path)
    raise SplitIOError(f"model input must be .parquet or .jsonl: {path}")


def deduplication_to_dict(result: DeduplicationResult) -> dict[str, object]:
    """Return the common deduplication manifest referenced by all six splits."""
    return {
        "schema_version": "1.0.0",
        "digest": deduplication_digest(result),
        "config": asdict(result.config),
        "fingerprints": [asdict(value) for value in result.fingerprints],
        "clusters": [asdict(value) for value in result.clusters],
        "near_duplicate_pairs": result.near_duplicate_pairs,
        "skipped_near_duplicate_buckets": result.skipped_near_duplicate_buckets,
    }


def render_deduplication_report(
    *,
    result: DeduplicationResult,
    manifests: Mapping[SplitStrategy, SplitManifest],
    unsupported: Mapping[SplitStrategy, str] | None = None,
) -> str:
    """Render a stable human-readable audit without copying raw prompt text."""
    duplicate_clusters = [cluster for cluster in result.clusters if len(cluster.query_ids) > 1]
    reason_counts: dict[str, int] = defaultdict(int)
    for cluster in duplicate_clusters:
        for reason in cluster.reasons:
            reason_counts[reason] += 1
    fingerprint_count = len(result.fingerprints)
    lines = [
        "# Deduplication and Leakage-Safe Split Report",
        "",
        "This report intentionally contains hashes and IDs, not raw prompt text.",
        "",
        "## Deduplication summary",
        "",
        "| Measure | Value |",
        "|---|---:|",
        f"| Queries fingerprinted | {fingerprint_count:,} |",
        f"| Atomic duplicate clusters | {len(result.clusters):,} |",
        f"| Multi-query duplicate clusters | {len(duplicate_clusters):,} |",
        f"| Confirmed near-duplicate pairs | {len(result.near_duplicate_pairs):,} |",
        "| Skipped over-broad near-duplicate buckets | "
        f"{result.skipped_near_duplicate_buckets:,} |",
        "",
        "## Duplicate evidence",
        "",
        "| Evidence | Clusters |",
        "|---|---:|",
    ]
    for reason in (
        "exact_prompt",
        "normalized_prompt",
        "source_identity",
        "augmentation_lineage",
        "near_duplicate",
    ):
        lines.append(f"| {reason} | {reason_counts.get(reason, 0):,} |")
    lines.extend(
        [
            "",
            "## Split summary",
            "",
            "| Strategy | Train queries | Validation queries | Test queries | Probes | "
            "Train models | Validation models | Test models | Shared models |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for strategy in sorted(manifests):
        manifest = manifests[strategy]
        lines.append(
            f"| {strategy} | {len(manifest.queries.train):,} | "
            f"{len(manifest.queries.validation):,} | {len(manifest.queries.test):,} | "
            f"{len(manifest.queries.probe):,} | {len(manifest.models.train):,} | "
            f"{len(manifest.models.validation):,} | {len(manifest.models.test):,} | "
            f"{len(manifest.models.shared):,} |"
        )
    unsupported_values = unsupported or {}
    if unsupported_values:
        lines.extend(["", "## Unsupported strategies", ""])
        for strategy in sorted(unsupported_values):
            lines.append(f"- `{strategy}`: {unsupported_values[strategy]}")
    lines.extend(
        [
            "",
            "## Leakage guarantees",
            "",
            "- Exact, normalized, source-identity, lineage, and accepted near-duplicate "
            "clusters remain atomic.",
            "- Probe clusters are isolated from train, validation, and final test traffic.",
            "- Model aliases resolve to one stable model ID.",
            "- Task, family, model, and temporal boundaries are checked for their "
            "corresponding strategies.",
            "- The manifests contain no wall-clock generation timestamp, so the same "
            "inputs, configuration, and seed produce identical bytes.",
            "",
        ]
    )
    return "\n".join(lines)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "--", value).strip("-.")
    if not slug:
        raise SplitIOError(f"value cannot be converted to a safe path component: {value!r}")
    return slug


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def write_split_bundle(
    *,
    storage_root: Path,
    repository_root: Path,
    config: SplitBuildConfig,
    deduplication: DeduplicationResult,
    manifests: Mapping[SplitStrategy, SplitManifest],
    unsupported: Mapping[SplitStrategy, str] | None = None,
) -> SplitBundlePaths:
    """Write generated artifacts to ignored local data storage or an external override."""
    root = validate_storage_root(
        storage_root=storage_root,
        repository_root=repository_root,
    )
    unsupported_values = unsupported or {}
    if set(manifests) & set(unsupported_values):
        raise SplitIOError("a strategy cannot be both generated and unsupported")
    if set(manifests) | set(unsupported_values) != set(SPLIT_STRATEGIES):
        raise SplitIOError("a complete Part 4 bundle must account for all six split strategies")

    manifest_directory = (
        root
        / "data"
        / "processed"
        / "part4"
        / "manifests"
        / "splits"
        / _slug(config.dataset_id)
        / _slug(config.dataset_revision)
        / _slug(config.manifest_version)
    )
    deduplication_manifest = manifest_directory / "deduplication.json"
    _write_text_atomic(
        deduplication_manifest,
        json.dumps(deduplication_to_dict(deduplication), indent=2, sort_keys=True) + "\n",
    )
    manifest_paths: list[Path] = []
    for strategy in sorted(manifests):
        path = manifest_directory / f"{strategy}.json"
        _write_text_atomic(path, manifests[strategy].to_json())
        manifest_paths.append(path)
    unsupported_paths: list[Path] = []
    for strategy in sorted(unsupported_values):
        path = manifest_directory / f"{strategy}.unsupported.json"
        _write_text_atomic(
            path,
            json.dumps(
                {
                    "manifest_version": config.manifest_version,
                    "strategy": strategy,
                    "status": "unsupported",
                    "reason": unsupported_values[strategy],
                    "dataset_id": config.dataset_id,
                    "dataset_revision": config.dataset_revision,
                    "canonical_schema_version": config.canonical_schema_version,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        unsupported_paths.append(path)

    report_path = (
        root
        / "data"
        / "processed"
        / "part4"
        / "reports"
        / f"{_slug(config.dataset_id)}_deduplication.md"
    )
    _write_text_atomic(
        report_path,
        render_deduplication_report(
            result=deduplication,
            manifests=manifests,
            unsupported=unsupported_values,
        ),
    )
    return SplitBundlePaths(
        manifest_directory=manifest_directory,
        deduplication_manifest=deduplication_manifest,
        split_manifests=tuple(manifest_paths),
        unsupported_manifests=tuple(unsupported_paths),
        deduplication_report=report_path,
    )
