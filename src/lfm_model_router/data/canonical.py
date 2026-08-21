"""Canonical routing-table schemas, validation, persistence, and price math."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any, cast

CANONICAL_SCHEMA_VERSION = "canonical-v1"
PRICE_UNIT_TOKENS = 1_000_000


class CanonicalDataError(ValueError):
    """Raised when canonical records violate a schema or relationship rule."""


class CanonicalDependencyError(RuntimeError):
    """Raised when optional Parquet support is unavailable."""


@dataclass(frozen=True, slots=True)
class PriceRates:
    """One model's versioned USD rates per million tokens."""

    input_per_million_usd: float
    cached_input_per_million_usd: float | None
    output_per_million_usd: float

    def validate(self) -> None:
        """Reject missing or negative price components."""
        if self.input_per_million_usd < 0.0:
            raise CanonicalDataError("input price must be non-negative")
        if (
            self.cached_input_per_million_usd is not None
            and self.cached_input_per_million_usd < 0.0
        ):
            raise CanonicalDataError("cached-input price must be non-negative")
        if self.output_per_million_usd < 0.0:
            raise CanonicalDataError("output price must be non-negative")


@dataclass(frozen=True, slots=True)
class CanonicalTables:
    """Six canonical tables held as value-preserving Python records."""

    queries: tuple[dict[str, object], ...]
    models: tuple[dict[str, object], ...]
    outcomes: tuple[dict[str, object], ...]
    price_history: tuple[dict[str, object], ...]
    probe_profiles: tuple[dict[str, object], ...]
    online_route_log: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class WrittenCanonicalTable:
    """Integrity metadata for one persisted canonical table."""

    name: str
    path: Path
    rows: int
    size_bytes: int
    sha256: str


def stable_canonical_id(prefix: str, *parts: object) -> str:
    """Return a readable deterministic identifier from immutable source coordinates."""
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:24]}"


def canonical_json(value: object) -> str:
    """Serialize source values deterministically without changing their types."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def compute_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    rates: PriceRates,
    cached_input_tokens: int = 0,
) -> float:
    """Recompute cost from immutable token counts and a replaceable price snapshot."""
    rates.validate()
    for field, value in (
        ("input_tokens", input_tokens),
        ("cached_input_tokens", cached_input_tokens),
        ("output_tokens", output_tokens),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CanonicalDataError(f"{field} must be a non-negative integer")
    if cached_input_tokens > input_tokens:
        raise CanonicalDataError("cached_input_tokens cannot exceed input_tokens")
    if cached_input_tokens and rates.cached_input_per_million_usd is None:
        raise CanonicalDataError("cached input tokens require a cached-input price")

    uncached_input_tokens = input_tokens - cached_input_tokens
    cached_rate = rates.cached_input_per_million_usd or 0.0
    return (
        uncached_input_tokens * rates.input_per_million_usd
        + cached_input_tokens * cached_rate
        + output_tokens * rates.output_per_million_usd
    ) / PRICE_UNIT_TOKENS


def _pyarrow() -> Any:
    try:
        return importlib.import_module("pyarrow")
    except ModuleNotFoundError as error:
        raise CanonicalDependencyError(
            'Canonical Parquet support requires: pip install -e ".[data]"'
        ) from error


def _parquet() -> Any:
    try:
        return importlib.import_module("pyarrow.parquet")
    except ModuleNotFoundError as error:
        raise CanonicalDependencyError(
            'Canonical Parquet support requires: pip install -e ".[data]"'
        ) from error


def query_schema() -> Any:
    """Return the versioned canonical query schema."""
    arrow = _pyarrow()
    return arrow.schema(
        [
            arrow.field("query_id", arrow.string(), nullable=False),
            arrow.field("source_dataset", arrow.string(), nullable=False),
            arrow.field("source_revision", arrow.string(), nullable=False),
            arrow.field("source_config", arrow.string(), nullable=False),
            arrow.field("source_split", arrow.string(), nullable=False),
            arrow.field("source_row_index", arrow.int64(), nullable=False),
            arrow.field("source_query_id", arrow.string()),
            arrow.field("prompt", arrow.large_string(), nullable=False),
            arrow.field("task", arrow.string(), nullable=False),
            arrow.field("ground_truth", arrow.large_string()),
            arrow.field("ground_truth_json", arrow.large_string(), nullable=False),
            arrow.field("metric", arrow.string(), nullable=False),
            arrow.field("modality", arrow.string(), nullable=False),
            arrow.field("choices_json", arrow.large_string()),
            arrow.field("metadata_json", arrow.large_string(), nullable=False),
            arrow.field("raw_source_json", arrow.large_string(), nullable=False),
            arrow.field("has_outcomes", arrow.bool_(), nullable=False),
            arrow.field("is_probe", arrow.bool_(), nullable=False),
            arrow.field("observed_at", arrow.timestamp("us", tz="UTC")),
        ],
        metadata={b"canonical_schema_version": CANONICAL_SCHEMA_VERSION.encode()},
    )


def model_schema() -> Any:
    """Return the versioned canonical model-registry schema."""
    arrow = _pyarrow()
    return arrow.schema(
        [
            arrow.field("model_id", arrow.string(), nullable=False),
            arrow.field("canonical_name", arrow.string(), nullable=False),
            arrow.field("provider", arrow.string(), nullable=False),
            arrow.field("developer", arrow.string(), nullable=False),
            arrow.field("family", arrow.string(), nullable=False),
            arrow.field("version", arrow.string(), nullable=False),
            arrow.field("aliases", arrow.list_(arrow.string()), nullable=False),
            arrow.field("api_model_id", arrow.string()),
            arrow.field("size_label", arrow.string()),
            arrow.field("parameter_count_billions", arrow.float64()),
            arrow.field("capabilities", arrow.list_(arrow.string()), nullable=False),
            arrow.field("description", arrow.large_string()),
            arrow.field("source_revision", arrow.string(), nullable=False),
            arrow.field("metadata_json", arrow.large_string(), nullable=False),
            arrow.field("available_at", arrow.timestamp("us", tz="UTC")),
        ],
        metadata={b"canonical_schema_version": CANONICAL_SCHEMA_VERSION.encode()},
    )


def outcome_schema() -> Any:
    """Return the versioned canonical per-query/model outcome schema."""
    arrow = _pyarrow()
    return arrow.schema(
        [
            arrow.field("outcome_id", arrow.string(), nullable=False),
            arrow.field("query_id", arrow.string(), nullable=False),
            arrow.field("model_id", arrow.string(), nullable=False),
            arrow.field("source_config", arrow.string(), nullable=False),
            arrow.field("source_split", arrow.string(), nullable=False),
            arrow.field("source_row_index", arrow.int64(), nullable=False),
            arrow.field("source_query_index", arrow.int64(), nullable=False),
            arrow.field("candidate_position", arrow.int8()),
            arrow.field("metric", arrow.string(), nullable=False),
            arrow.field("response", arrow.large_string()),
            arrow.field("score", arrow.float64()),
            arrow.field("total_tokens", arrow.int64()),
            arrow.field("input_tokens", arrow.int64()),
            arrow.field("output_tokens", arrow.int64()),
            arrow.field("latency_seconds", arrow.float64()),
            arrow.field("succeeded", arrow.bool_(), nullable=False),
            arrow.field("failure_type", arrow.string()),
            arrow.field("metadata_json", arrow.large_string(), nullable=False),
        ],
        metadata={b"canonical_schema_version": CANONICAL_SCHEMA_VERSION.encode()},
    )


def price_history_schema() -> Any:
    """Return the versioned price-history schema."""
    arrow = _pyarrow()
    return arrow.schema(
        [
            arrow.field("price_id", arrow.string(), nullable=False),
            arrow.field("price_snapshot_id", arrow.string(), nullable=False),
            arrow.field("model_id", arrow.string(), nullable=False),
            arrow.field("effective_at", arrow.timestamp("us", tz="UTC"), nullable=False),
            arrow.field("currency", arrow.string(), nullable=False),
            arrow.field("unit_tokens", arrow.int64(), nullable=False),
            arrow.field("input_per_unit", arrow.float64(), nullable=False),
            arrow.field("cached_input_per_unit", arrow.float64()),
            arrow.field("output_per_unit", arrow.float64(), nullable=False),
            arrow.field("source", arrow.string(), nullable=False),
            arrow.field("source_revision", arrow.string(), nullable=False),
            arrow.field("metadata_json", arrow.large_string(), nullable=False),
        ],
        metadata={b"canonical_schema_version": CANONICAL_SCHEMA_VERSION.encode()},
    )


def probe_profile_schema() -> Any:
    """Return the versioned behavioral-probe observation schema."""
    arrow = _pyarrow()
    return arrow.schema(
        [
            arrow.field("probe_profile_id", arrow.string(), nullable=False),
            arrow.field("probe_set_id", arrow.string(), nullable=False),
            arrow.field("query_id", arrow.string(), nullable=False),
            arrow.field("model_id", arrow.string(), nullable=False),
            arrow.field("outcome_id", arrow.string()),
            arrow.field("score", arrow.float64()),
            arrow.field("input_tokens", arrow.int64()),
            arrow.field("output_tokens", arrow.int64()),
            arrow.field("latency_seconds", arrow.float64()),
            arrow.field("observed_at", arrow.timestamp("us", tz="UTC")),
            arrow.field("metadata_json", arrow.large_string(), nullable=False),
        ],
        metadata={b"canonical_schema_version": CANONICAL_SCHEMA_VERSION.encode()},
    )


def online_route_log_schema() -> Any:
    """Return the versioned online routing-event schema."""
    arrow = _pyarrow()
    return arrow.schema(
        [
            arrow.field("route_id", arrow.string(), nullable=False),
            arrow.field("query_id", arrow.string(), nullable=False),
            arrow.field("event_time", arrow.timestamp("us", tz="UTC"), nullable=False),
            arrow.field("candidate_model_ids", arrow.list_(arrow.string()), nullable=False),
            arrow.field("selected_model_id", arrow.string(), nullable=False),
            arrow.field("selection_probability", arrow.float64(), nullable=False),
            arrow.field("predicted_quality", arrow.float64()),
            arrow.field("predicted_output_tokens", arrow.float64()),
            arrow.field("predicted_latency_seconds", arrow.float64()),
            arrow.field("feedback_score", arrow.float64()),
            arrow.field("feedback_received_at", arrow.timestamp("us", tz="UTC")),
            arrow.field("metadata_json", arrow.large_string(), nullable=False),
        ],
        metadata={b"canonical_schema_version": CANONICAL_SCHEMA_VERSION.encode()},
    )


def canonical_schemas() -> dict[str, Any]:
    """Return all six schemas under their stable table names."""
    return {
        "queries": query_schema(),
        "models": model_schema(),
        "outcomes": outcome_schema(),
        "price_history": price_history_schema(),
        "probe_profiles": probe_profile_schema(),
        "online_route_log": online_route_log_schema(),
    }


def _require_string(record: Mapping[str, object], field: str, *, context: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CanonicalDataError(f"{context}.{field} must be a non-empty string")
    return value


def _require_non_negative_integer(
    value: object, *, field: str, context: str, nullable: bool
) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        suffix = " or null" if nullable else ""
        raise CanonicalDataError(f"{context}.{field} must be a non-negative integer{suffix}")


def _require_probability(value: object, *, field: str, context: str, nullable: bool) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= value <= 1.0:
        suffix = " or null" if nullable else ""
        raise CanonicalDataError(f"{context}.{field} must be in [0, 1]{suffix}")


def _require_non_negative_number(
    value: object, *, field: str, context: str, nullable: bool
) -> None:
    if value is None and nullable:
        return
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not isfinite(value)
        or value < 0.0
    ):
        suffix = " or null" if nullable else ""
        raise CanonicalDataError(f"{context}.{field} must be non-negative{suffix}")


def _require_timezone_aware(value: object, *, field: str, context: str, nullable: bool) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, datetime) or value.tzinfo is None:
        suffix = " or null" if nullable else ""
        raise CanonicalDataError(f"{context}.{field} must include a timezone{suffix}")


def _unique_ids(records: Sequence[Mapping[str, object]], *, field: str, table: str) -> set[str]:
    identifiers: set[str] = set()
    for index, record in enumerate(records):
        identifier = _require_string(record, field, context=f"{table}[{index}]")
        if identifier in identifiers:
            raise CanonicalDataError(f"duplicate {table}.{field}: {identifier}")
        identifiers.add(identifier)
    return identifiers


def _normalize_alias(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_canonical_tables(tables: CanonicalTables) -> None:
    """Validate values, IDs, ranges, and every cross-table relationship."""
    query_ids = _unique_ids(tables.queries, field="query_id", table="queries")
    model_ids = _unique_ids(tables.models, field="model_id", table="models")
    outcome_ids = _unique_ids(tables.outcomes, field="outcome_id", table="outcomes")
    _unique_ids(tables.price_history, field="price_id", table="price_history")
    _unique_ids(tables.probe_profiles, field="probe_profile_id", table="probe_profiles")
    _unique_ids(tables.online_route_log, field="route_id", table="online_route_log")

    allowed_modalities = {"text", "image", "video", "timeseries"}
    allowed_splits = {"train", "valid", "test"}
    for index, query in enumerate(tables.queries):
        context = f"queries[{index}]"
        for field in (
            "source_dataset",
            "source_revision",
            "source_config",
            "source_split",
            "prompt",
            "task",
            "metric",
            "modality",
            "ground_truth_json",
            "metadata_json",
            "raw_source_json",
        ):
            _require_string(query, field, context=context)
        if query["source_split"] not in allowed_splits:
            raise CanonicalDataError(f"{context}.source_split is not recognized")
        if query["modality"] not in allowed_modalities:
            raise CanonicalDataError(f"{context}.modality is not recognized")
        _require_non_negative_integer(
            query.get("source_row_index"),
            field="source_row_index",
            context=context,
            nullable=False,
        )
        for field in ("has_outcomes", "is_probe"):
            if not isinstance(query.get(field), bool):
                raise CanonicalDataError(f"{context}.{field} must be a boolean")
        _require_timezone_aware(
            query.get("observed_at"),
            field="observed_at",
            context=context,
            nullable=True,
        )

    alias_owners: dict[str, str] = {}
    for index, model in enumerate(tables.models):
        context = f"models[{index}]"
        model_id = cast(str, model["model_id"])
        for field in (
            "canonical_name",
            "provider",
            "developer",
            "family",
            "version",
            "source_revision",
            "metadata_json",
        ):
            _require_string(model, field, context=context)
        aliases = model.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            raise CanonicalDataError(f"{context}.aliases must be a non-empty list")
        for alias in aliases:
            if not isinstance(alias, str) or not alias.strip():
                raise CanonicalDataError(f"{context}.aliases contains an empty value")
            normalized = _normalize_alias(alias)
            owner = alias_owners.get(normalized)
            if owner is not None and owner != model_id:
                raise CanonicalDataError(
                    f"model alias {alias!r} maps to both {owner!r} and {model_id!r}"
                )
            alias_owners[normalized] = model_id
        capabilities = model.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            raise CanonicalDataError(f"{context}.capabilities must be a non-empty list")
        if any(
            not isinstance(capability, str) or not capability.strip() for capability in capabilities
        ):
            raise CanonicalDataError(f"{context}.capabilities contains an empty value")
        _require_non_negative_number(
            model.get("parameter_count_billions"),
            field="parameter_count_billions",
            context=context,
            nullable=True,
        )
        _require_timezone_aware(
            model.get("available_at"),
            field="available_at",
            context=context,
            nullable=True,
        )

    for index, outcome in enumerate(tables.outcomes):
        context = f"outcomes[{index}]"
        query_id = _require_string(outcome, "query_id", context=context)
        model_id = _require_string(outcome, "model_id", context=context)
        if query_id not in query_ids:
            raise CanonicalDataError(f"{context}.query_id references unknown query {query_id}")
        if model_id not in model_ids:
            raise CanonicalDataError(f"{context}.model_id references unknown model {model_id}")
        for field in (
            "source_config",
            "source_split",
            "metric",
            "metadata_json",
        ):
            _require_string(outcome, field, context=context)
        _require_probability(outcome.get("score"), field="score", context=context, nullable=True)
        for field in ("source_row_index", "source_query_index"):
            _require_non_negative_integer(
                outcome.get(field), field=field, context=context, nullable=False
            )
        _require_non_negative_integer(
            outcome.get("candidate_position"),
            field="candidate_position",
            context=context,
            nullable=True,
        )
        for field in ("total_tokens", "input_tokens", "output_tokens"):
            _require_non_negative_integer(
                outcome.get(field), field=field, context=context, nullable=True
            )
        input_tokens = outcome.get("input_tokens")
        output_tokens = outcome.get("output_tokens")
        total_tokens = outcome.get("total_tokens")
        if (
            isinstance(input_tokens, int)
            and isinstance(output_tokens, int)
            and isinstance(total_tokens, int)
            and total_tokens != input_tokens + output_tokens
        ):
            raise CanonicalDataError(
                f"{context}.total_tokens does not equal input_tokens + output_tokens"
            )
        _require_non_negative_number(
            outcome.get("latency_seconds"),
            field="latency_seconds",
            context=context,
            nullable=True,
        )
        if not isinstance(outcome.get("succeeded"), bool):
            raise CanonicalDataError(f"{context}.succeeded must be a boolean")

    outcome_query_ids = {cast(str, outcome["query_id"]) for outcome in tables.outcomes}
    for index, query in enumerate(tables.queries):
        query_id = cast(str, query["query_id"])
        if cast(bool, query["has_outcomes"]) != (query_id in outcome_query_ids):
            raise CanonicalDataError(
                f"queries[{index}].has_outcomes disagrees with the outcome table"
            )

    for index, price in enumerate(tables.price_history):
        context = f"price_history[{index}]"
        model_id = _require_string(price, "model_id", context=context)
        if model_id not in model_ids:
            raise CanonicalDataError(f"{context}.model_id references unknown model {model_id}")
        for field in (
            "price_snapshot_id",
            "currency",
            "source",
            "source_revision",
            "metadata_json",
        ):
            _require_string(price, field, context=context)
        _require_non_negative_integer(
            price.get("unit_tokens"), field="unit_tokens", context=context, nullable=False
        )
        for field in ("input_per_unit", "cached_input_per_unit", "output_per_unit"):
            value = price.get(field)
            if value is None and field == "cached_input_per_unit":
                continue
            _require_non_negative_number(
                value,
                field=field,
                context=context,
                nullable=False,
            )
        _require_timezone_aware(
            price.get("effective_at"),
            field="effective_at",
            context=context,
            nullable=False,
        )

    outcomes_by_id = {cast(str, outcome["outcome_id"]): outcome for outcome in tables.outcomes}
    for index, profile in enumerate(tables.probe_profiles):
        context = f"probe_profiles[{index}]"
        for field in ("probe_set_id", "metadata_json"):
            _require_string(profile, field, context=context)
        query_id = _require_string(profile, "query_id", context=context)
        model_id = _require_string(profile, "model_id", context=context)
        if query_id not in query_ids or model_id not in model_ids:
            raise CanonicalDataError(f"{context} references an unknown query or model")
        outcome_id = profile.get("outcome_id")
        if outcome_id is not None and outcome_id not in outcome_ids:
            raise CanonicalDataError(f"{context}.outcome_id references an unknown outcome")
        if outcome_id is not None:
            outcome = outcomes_by_id[outcome_id]
            if outcome["query_id"] != query_id or outcome["model_id"] != model_id:
                raise CanonicalDataError(f"{context}.outcome_id does not match its query and model")
        _require_probability(profile.get("score"), field="score", context=context, nullable=True)
        for field in ("input_tokens", "output_tokens"):
            _require_non_negative_integer(
                profile.get(field), field=field, context=context, nullable=True
            )
        _require_non_negative_number(
            profile.get("latency_seconds"),
            field="latency_seconds",
            context=context,
            nullable=True,
        )
        _require_timezone_aware(
            profile.get("observed_at"),
            field="observed_at",
            context=context,
            nullable=True,
        )

    for index, route in enumerate(tables.online_route_log):
        context = f"online_route_log[{index}]"
        _require_string(route, "metadata_json", context=context)
        query_id = _require_string(route, "query_id", context=context)
        selected_model_id = _require_string(route, "selected_model_id", context=context)
        if query_id not in query_ids or selected_model_id not in model_ids:
            raise CanonicalDataError(f"{context} references an unknown query or model")
        candidates = route.get("candidate_model_ids")
        if not isinstance(candidates, list) or not candidates:
            raise CanonicalDataError(f"{context}.candidate_model_ids must not be empty")
        if any(candidate not in model_ids for candidate in candidates):
            raise CanonicalDataError(f"{context} contains an unknown candidate model")
        if selected_model_id not in candidates:
            raise CanonicalDataError(f"{context}.selected_model_id is not a candidate")
        _require_probability(
            route.get("selection_probability"),
            field="selection_probability",
            context=context,
            nullable=False,
        )
        if route["selection_probability"] == 0:
            raise CanonicalDataError(f"{context}.selection_probability must be greater than zero")
        _require_probability(
            route.get("predicted_quality"),
            field="predicted_quality",
            context=context,
            nullable=True,
        )
        _require_probability(
            route.get("feedback_score"),
            field="feedback_score",
            context=context,
            nullable=True,
        )
        for field in ("predicted_output_tokens", "predicted_latency_seconds"):
            _require_non_negative_number(
                route.get(field), field=field, context=context, nullable=True
            )
        _require_timezone_aware(
            route.get("event_time"),
            field="event_time",
            context=context,
            nullable=False,
        )
        _require_timezone_aware(
            route.get("feedback_received_at"),
            field="feedback_received_at",
            context=context,
            nullable=True,
        )


def _json_ready(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def write_jsonl_debug(records: Sequence[Mapping[str, object]], *, path: Path, limit: int) -> None:
    """Write a bounded deterministic JSONL debug view using atomic replacement."""
    if limit < 0:
        raise CanonicalDataError("debug JSONL limit must be non-negative")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as destination:
        for record in records[:limit]:
            destination.write(
                json.dumps(
                    _json_ready(dict(record)),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )
    temporary.replace(path)


def write_canonical_parquet(
    *,
    name: str,
    records: Sequence[Mapping[str, object]],
    schema: Any,
    path: Path,
) -> WrittenCanonicalTable:
    """Write one canonical table with a fixed schema and return integrity metadata."""
    arrow = _pyarrow()
    parquet = _parquet()
    table = arrow.Table.from_pylist([dict(record) for record in records], schema=schema)
    if table.schema != schema:
        raise CanonicalDataError(f"{name} table schema differs from canonical schema")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    parquet.write_table(
        table,
        temporary,
        compression="zstd",
        use_dictionary=True,
        write_statistics=True,
    )
    temporary.replace(path)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return WrittenCanonicalTable(
        name=name,
        path=path,
        rows=table.num_rows,
        size_bytes=path.stat().st_size,
        sha256=digest.hexdigest(),
    )
