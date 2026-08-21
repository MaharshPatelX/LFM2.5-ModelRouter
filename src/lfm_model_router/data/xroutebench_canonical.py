"""Value-preserving xRouteBench transformation into the six canonical tables."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from lfm_model_router.data.adapters.xroutebench import XRouteBenchAdapter
from lfm_model_router.data.canonical import (
    CANONICAL_SCHEMA_VERSION,
    PRICE_UNIT_TOKENS,
    CanonicalDataError,
    CanonicalTables,
    WrittenCanonicalTable,
    canonical_json,
    canonical_schemas,
    stable_canonical_id,
    validate_canonical_tables,
    write_canonical_parquet,
    write_jsonl_debug,
)

QUERY_CONFIG_MODALITIES = {
    "llmrouter_generic_queries": "text",
    "memory_locomo_queries": "text",
    "memory_longmemeval_queries": "text",
    "multimodal_geometry3k_queries": "image",
    "multimodal_mathvista_queries": "image",
    "personalized_queries": "text",
    "timeseries_queries": "timeseries",
    "video_queries": "video",
}
STANDARD_OUTCOME_CONFIGS = (
    "llmrouter_generic",
    "memory_locomo",
    "memory_longmemeval",
    "multimodal_geometry3k",
    "multimodal_mathvista",
    "timeseries",
    "video",
)
QUERY_FIELDS = ("task_name", "query", "ground_truth", "metric", "choices", "task_id")


@dataclass(frozen=True, slots=True)
class XRouteBenchCanonicalBuild:
    """Canonical records plus source provenance needed to persist a build."""

    tables: CanonicalTables
    source_dataset: str
    source_revision: str
    source_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class WrittenCanonicalDataset:
    """Paths and integrity metadata for one complete canonical build."""

    root: Path
    manifest_path: Path
    tables: tuple[WrittenCanonicalTable, ...]


def _normalize_alias(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _alias_sort_key(value: str) -> tuple[str, str]:
    """Order aliases deterministically even when normalization makes them equal."""
    return (_normalize_alias(value), value)


def _source_query_id(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value)
    return rendered if rendered else None


def _ground_truth(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return canonical_json(value)


def _metadata(raw: dict[str, object], *, excluded: set[str]) -> str:
    return canonical_json({key: value for key, value in raw.items() if key not in excluded})


def _parameter_billions(size_label: object) -> float | None:
    if not isinstance(size_label, str):
        return None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)B", size_label, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _developer(api_model_id: str) -> str:
    if "/" not in api_model_id:
        return "unknown"
    return api_model_id.split("/", maxsplit=1)[0].casefold()


def _family(identifier: str) -> str:
    """Infer a conservative family label only from the source model identifier."""
    name = identifier.rsplit("/", maxsplit=1)[-1].casefold()
    if name.startswith("meta-llama-"):
        name = name.removeprefix("meta-")
    if name.startswith("llama3-"):
        name = f"llama-3-{name.removeprefix('llama3-')}"
    prefixes = (
        "qwen2.5-coder",
        "qwen2.5",
        "qwen3-next",
        "qwen3-coder",
        "llama-3.3",
        "llama-3",
        "llama-4",
        "gemma-2",
        "mistral-large-3",
        "mistral-small-3",
        "mistral",
        "ministral",
        "mixtral",
        "devstral",
        "gpt-oss",
        "deepseek-v3",
        "cogito-v2",
        "kimi-k2",
        "nemotron-3",
        "nvidia-nemotron",
        "seed-oss",
        "eurollm",
        "bielik",
        "marin",
        "stockmark-2",
        "step-3.5",
        "rnj-1",
    )
    for prefix in prefixes:
        if name.startswith(prefix):
            return prefix
    return name


def _aware_datetime(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CanonicalDataError(f"source manifest {field} must be a timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CanonicalDataError(f"source manifest {field} is not ISO-8601: {value}") from error
    if parsed.tzinfo is None:
        raise CanonicalDataError(f"source manifest {field} must include a timezone")
    return parsed


def _read_source_metadata(path: Path) -> tuple[dict[str, object], str]:
    try:
        raw_bytes = path.read_bytes()
        value = json.loads(raw_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise CanonicalDataError(f"could not read source manifest at {path}: {error}") from error
    if not isinstance(value, dict):
        raise CanonicalDataError("source manifest must be a JSON object")
    return cast(dict[str, object], value), hashlib.sha256(raw_bytes).hexdigest()


def _build_queries(
    *, adapter: XRouteBenchAdapter
) -> tuple[
    tuple[dict[str, object], ...],
    dict[tuple[str, str, int], str],
    dict[tuple[str, str, int], dict[str, object]],
]:
    records: list[dict[str, object]] = []
    query_ids: dict[tuple[str, str, int], str] = {}
    raw_queries: dict[tuple[str, str, int], dict[str, object]] = {}
    available_files = {(item.config, item.split) for item in adapter.manifest.files}

    for query_config, modality in QUERY_CONFIG_MODALITIES.items():
        base_config = query_config.removesuffix("_queries")
        for split in ("train", "valid", "test"):
            if (query_config, split) not in available_files:
                continue
            has_outcomes = (base_config, split) in available_files
            for row_index, raw in enumerate(adapter.iter_split(query_config, split)):
                query_id = stable_canonical_id(
                    "qry",
                    adapter.manifest.dataset_id,
                    adapter.manifest.revision,
                    query_config,
                    split,
                    row_index,
                )
                coordinate = (base_config, split, row_index)
                query_ids[coordinate] = query_id
                raw_queries[coordinate] = raw
                prompt = raw.get("query")
                task = raw.get("task_name")
                metric = raw.get("metric")
                if not isinstance(prompt, str) or not prompt:
                    raise CanonicalDataError(
                        f"{query_config}/{split}[{row_index}].query must not be empty"
                    )
                if not isinstance(task, str) or not task:
                    raise CanonicalDataError(
                        f"{query_config}/{split}[{row_index}].task_name must not be empty"
                    )
                if not isinstance(metric, str) or not metric:
                    raise CanonicalDataError(
                        f"{query_config}/{split}[{row_index}].metric must not be empty"
                    )
                records.append(
                    {
                        "query_id": query_id,
                        "source_dataset": adapter.manifest.dataset_id,
                        "source_revision": adapter.manifest.revision,
                        "source_config": query_config,
                        "source_split": split,
                        "source_row_index": row_index,
                        "source_query_id": _source_query_id(raw.get("task_id")),
                        "prompt": prompt,
                        "task": task,
                        "ground_truth": _ground_truth(raw.get("ground_truth")),
                        "ground_truth_json": canonical_json(raw.get("ground_truth")),
                        "metric": metric,
                        "modality": modality,
                        "choices_json": canonical_json(raw.get("choices")),
                        "metadata_json": _metadata(raw, excluded=set(QUERY_FIELDS)),
                        "raw_source_json": canonical_json(raw),
                        "has_outcomes": has_outcomes,
                        "is_probe": False,
                        "observed_at": None,
                    }
                )
    return tuple(records), query_ids, raw_queries


def _personalized_aliases(adapter: XRouteBenchAdapter) -> set[str]:
    aliases: set[str] = set()
    for split in ("train", "test"):
        for raw in adapter.iter_split("personalized", split):
            for field in ("model_1", "model_2"):
                value = raw.get(field)
                if not isinstance(value, str) or not value:
                    raise CanonicalDataError(f"personalized/{split}.{field} must not be empty")
                aliases.add(value)
    return aliases


def _build_models(
    *, adapter: XRouteBenchAdapter, personalized_aliases: set[str]
) -> tuple[tuple[dict[str, object], ...], dict[str, str]]:
    working: list[dict[str, object]] = []
    alias_to_model: dict[str, str] = {}

    for raw in adapter.iter_split("llm_candidates", "train"):
        model_name = raw.get("model_name")
        api_model_id = raw.get("api_model_id")
        service = raw.get("service")
        if not isinstance(model_name, str) or not model_name:
            raise CanonicalDataError("llm_candidates.model_name must not be empty")
        if not isinstance(api_model_id, str) or not api_model_id:
            raise CanonicalDataError(f"candidate {model_name} has no api_model_id")
        if not isinstance(service, str) or not service:
            raise CanonicalDataError(f"candidate {model_name} has no service")
        model_id = stable_canonical_id(
            "mdl", adapter.manifest.dataset_id, _normalize_alias(api_model_id)
        )
        aliases = {model_name, api_model_id}
        for alias in aliases:
            normalized = _normalize_alias(alias)
            owner = alias_to_model.get(normalized)
            if owner is not None and owner != model_id:
                raise CanonicalDataError(f"candidate alias collision: {alias}")
            alias_to_model[normalized] = model_id
        working.append(
            {
                "model_id": model_id,
                "canonical_name": model_name,
                "provider": service,
                "developer": _developer(api_model_id),
                "family": _family(api_model_id),
                "version": model_name,
                "aliases": aliases,
                "api_model_id": api_model_id,
                "size_label": raw.get("size"),
                "parameter_count_billions": _parameter_billions(raw.get("size")),
                "capabilities": ["text"],
                "description": raw.get("description"),
                "source_revision": adapter.manifest.revision,
                "metadata_json": canonical_json(
                    {"source_config": "llm_candidates", "raw_source": raw}
                ),
                "available_at": None,
            }
        )

    for alias in sorted(personalized_aliases, key=_alias_sort_key):
        normalized = _normalize_alias(alias)
        if normalized in alias_to_model:
            model_id = alias_to_model[normalized]
            record = next(item for item in working if item["model_id"] == model_id)
            cast(set[str], record["aliases"]).add(alias)
            continue
        model_id = stable_canonical_id("mdl", adapter.manifest.dataset_id, normalized)
        alias_to_model[normalized] = model_id
        working.append(
            {
                "model_id": model_id,
                "canonical_name": alias,
                "provider": _developer(alias),
                "developer": _developer(alias),
                "family": _family(alias),
                "version": alias.rsplit("/", maxsplit=1)[-1],
                "aliases": {alias},
                "api_model_id": alias,
                "size_label": None,
                "parameter_count_billions": None,
                "capabilities": ["text"],
                "description": None,
                "source_revision": adapter.manifest.revision,
                "metadata_json": canonical_json(
                    {"source_config": "personalized", "observed_alias": alias}
                ),
                "available_at": None,
            }
        )

    records: list[dict[str, object]] = []
    for item in working:
        record = dict(item)
        record["aliases"] = sorted(cast(set[str], item["aliases"]), key=_alias_sort_key)
        records.append(record)
    records.sort(key=lambda item: cast(str, item["model_id"]))
    return tuple(records), alias_to_model


def _validate_query_copy(
    *,
    raw_outcome: dict[str, object],
    raw_query: dict[str, object],
    context: str,
) -> None:
    mismatches = [field for field in QUERY_FIELDS if raw_outcome.get(field) != raw_query.get(field)]
    if mismatches:
        raise CanonicalDataError(
            f"{context} differs from its query row in fields: {', '.join(mismatches)}"
        )


def _model_id(alias_to_model: dict[str, str], alias: object, *, context: str) -> str:
    if not isinstance(alias, str) or not alias:
        raise CanonicalDataError(f"{context} model alias must not be empty")
    model_id = alias_to_model.get(_normalize_alias(alias))
    if model_id is None:
        raise CanonicalDataError(f"{context} references unknown model alias {alias!r}")
    return model_id


def _build_standard_outcomes(
    *,
    adapter: XRouteBenchAdapter,
    query_ids: dict[tuple[str, str, int], str],
    raw_queries: dict[tuple[str, str, int], dict[str, object]],
    alias_to_model: dict[str, str],
) -> list[dict[str, object]]:
    outcomes: list[dict[str, object]] = []
    for config in STANDARD_OUTCOME_CONFIGS:
        for split in ("train", "test"):
            query_counts: Counter[int] = Counter()
            for row_index, raw in enumerate(adapter.iter_split(config, split)):
                source_query_index = raw.get("embedding_id")
                if not isinstance(source_query_index, int) or isinstance(source_query_index, bool):
                    raise CanonicalDataError(
                        f"{config}/{split}[{row_index}].embedding_id must be an integer"
                    )
                coordinate = (config, split, source_query_index)
                query_id = query_ids.get(coordinate)
                raw_query = raw_queries.get(coordinate)
                if query_id is None or raw_query is None:
                    raise CanonicalDataError(
                        f"{config}/{split}[{row_index}] references missing query index "
                        f"{source_query_index}"
                    )
                _validate_query_copy(
                    raw_outcome=raw,
                    raw_query=raw_query,
                    context=f"{config}/{split}[{row_index}]",
                )
                model_id = _model_id(
                    alias_to_model,
                    raw.get("model_name"),
                    context=f"{config}/{split}[{row_index}]",
                )
                response = raw.get("response")
                succeeded = response is not None
                metadata_fields = {
                    "embedding_id",
                    "category",
                    "conversation_id",
                }
                outcomes.append(
                    {
                        "outcome_id": stable_canonical_id(
                            "out",
                            adapter.manifest.dataset_id,
                            adapter.manifest.revision,
                            config,
                            split,
                            row_index,
                        ),
                        "query_id": query_id,
                        "model_id": model_id,
                        "source_config": config,
                        "source_split": split,
                        "source_row_index": row_index,
                        "source_query_index": source_query_index,
                        "candidate_position": None,
                        "metric": raw["metric"],
                        "response": response,
                        "score": float(cast(int | float, raw["performance"])),
                        "total_tokens": raw.get("token_num"),
                        "input_tokens": raw.get("input_tokens"),
                        "output_tokens": raw.get("output_tokens"),
                        "latency_seconds": raw.get("response_time"),
                        "succeeded": succeeded,
                        "failure_type": None if succeeded else "missing_response",
                        "metadata_json": canonical_json(
                            {key: raw.get(key) for key in metadata_fields if key in raw}
                        ),
                    }
                )
                query_counts[source_query_index] += 1
            invalid_counts = {
                query_index: count for query_index, count in query_counts.items() if count != 18
            }
            if invalid_counts:
                raise CanonicalDataError(
                    f"{config}/{split} must contain exactly 18 outcomes per query"
                )
    return outcomes


def _build_personalized_outcomes(
    *,
    adapter: XRouteBenchAdapter,
    query_ids: dict[tuple[str, str, int], str],
    raw_queries: dict[tuple[str, str, int], dict[str, object]],
    alias_to_model: dict[str, str],
) -> list[dict[str, object]]:
    outcomes: list[dict[str, object]] = []
    for split in ("train", "test"):
        for row_index, raw in enumerate(adapter.iter_split("personalized", split)):
            source_query_index = raw.get("embedding_id")
            if not isinstance(source_query_index, int) or isinstance(source_query_index, bool):
                raise CanonicalDataError(
                    f"personalized/{split}[{row_index}].embedding_id must be an integer"
                )
            coordinate = ("personalized", split, source_query_index)
            query_id = query_ids.get(coordinate)
            raw_query = raw_queries.get(coordinate)
            if query_id is None or raw_query is None:
                raise CanonicalDataError(
                    f"personalized/{split}[{row_index}] references missing query index "
                    f"{source_query_index}"
                )
            for field in ("task_name", "task_id", "query", "metric"):
                if raw.get(field) != raw_query.get(field):
                    raise CanonicalDataError(
                        f"personalized/{split}[{row_index}].{field} differs from query row"
                    )
            judge = raw.get("judge")
            if judge not in (1, 2):
                raise CanonicalDataError(f"personalized/{split}[{row_index}].judge must be 1 or 2")
            for position in (1, 2):
                model_alias = raw.get(f"model_{position}")
                response = raw.get(f"answer_{position}")
                succeeded = response is not None
                outcomes.append(
                    {
                        "outcome_id": stable_canonical_id(
                            "out",
                            adapter.manifest.dataset_id,
                            adapter.manifest.revision,
                            "personalized",
                            split,
                            row_index,
                            position,
                        ),
                        "query_id": query_id,
                        "model_id": _model_id(
                            alias_to_model,
                            model_alias,
                            context=f"personalized/{split}[{row_index}].model_{position}",
                        ),
                        "source_config": "personalized",
                        "source_split": split,
                        "source_row_index": row_index,
                        "source_query_index": source_query_index,
                        "candidate_position": position,
                        "metric": raw["metric"],
                        "response": response,
                        "score": 1.0 if judge == position else 0.0,
                        "total_tokens": None,
                        "input_tokens": None,
                        "output_tokens": None,
                        "latency_seconds": None,
                        "succeeded": succeeded,
                        "failure_type": None if succeeded else "missing_response",
                        "metadata_json": canonical_json(
                            {
                                "embedding_id": source_query_index,
                                "judge": judge,
                                "persona_id": raw.get("persona_id"),
                                "persona": raw.get("persona"),
                                "paired_model_alias": raw.get(f"model_{3 - position}"),
                            }
                        ),
                    }
                )
    return outcomes


def _build_prices(
    *,
    adapter: XRouteBenchAdapter,
    alias_to_model: dict[str, str],
    effective_at: datetime,
) -> tuple[dict[str, object], ...]:
    snapshot_id = stable_canonical_id(
        "price-snapshot", adapter.manifest.dataset_id, adapter.manifest.revision
    )
    prices: list[dict[str, object]] = []
    for raw in adapter.iter_split("llm_candidates", "train"):
        model_id = _model_id(
            alias_to_model,
            raw.get("model_name"),
            context="llm_candidates",
        )
        prices.append(
            {
                "price_id": stable_canonical_id("price", snapshot_id, model_id),
                "price_snapshot_id": snapshot_id,
                "model_id": model_id,
                "effective_at": effective_at,
                "currency": "USD",
                "unit_tokens": PRICE_UNIT_TOKENS,
                "input_per_unit": float(cast(int | float, raw["input_price_per_1m"])),
                "cached_input_per_unit": None,
                "output_per_unit": float(cast(int | float, raw["output_price_per_1m"])),
                "source": "xroutebench:llm_candidates",
                "source_revision": adapter.manifest.revision,
                "metadata_json": canonical_json(
                    {
                        "model_name": raw.get("model_name"),
                        "api_model_id": raw.get("api_model_id"),
                    }
                ),
            }
        )
    return tuple(prices)


def build_xroutebench_canonical(
    *, adapter: XRouteBenchAdapter, source_manifest_path: Path
) -> XRouteBenchCanonicalBuild:
    """Transform and validate every pinned xRouteBench source table."""
    source_metadata, source_manifest_sha256 = _read_source_metadata(source_manifest_path)
    if source_metadata.get("dataset_id") != adapter.manifest.dataset_id:
        raise CanonicalDataError("adapter and source manifest dataset IDs differ")
    if source_metadata.get("revision") != adapter.manifest.revision:
        raise CanonicalDataError("adapter and source manifest revisions differ")
    effective_at = _aware_datetime(
        source_metadata.get("revision_last_modified_utc"),
        field="revision_last_modified_utc",
    )

    queries, query_ids, raw_queries = _build_queries(adapter=adapter)
    personalized_aliases = _personalized_aliases(adapter)
    models, alias_to_model = _build_models(
        adapter=adapter,
        personalized_aliases=personalized_aliases,
    )
    outcomes = _build_standard_outcomes(
        adapter=adapter,
        query_ids=query_ids,
        raw_queries=raw_queries,
        alias_to_model=alias_to_model,
    )
    outcomes.extend(
        _build_personalized_outcomes(
            adapter=adapter,
            query_ids=query_ids,
            raw_queries=raw_queries,
            alias_to_model=alias_to_model,
        )
    )
    tables = CanonicalTables(
        queries=queries,
        models=models,
        outcomes=tuple(outcomes),
        price_history=_build_prices(
            adapter=adapter,
            alias_to_model=alias_to_model,
            effective_at=effective_at,
        ),
        probe_profiles=(),
        online_route_log=(),
    )
    validate_canonical_tables(tables)
    return XRouteBenchCanonicalBuild(
        tables=tables,
        source_dataset=adapter.manifest.dataset_id,
        source_revision=adapter.manifest.revision,
        source_manifest_sha256=source_manifest_sha256,
    )


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def write_xroutebench_canonical(
    *, build: XRouteBenchCanonicalBuild, output_root: Path, debug_limit: int
) -> WrittenCanonicalDataset:
    """Persist all six Parquet tables, bounded JSONL debug views, and a manifest."""
    validate_canonical_tables(build.tables)
    schemas = canonical_schemas()
    table_records = {
        "queries": build.tables.queries,
        "models": build.tables.models,
        "outcomes": build.tables.outcomes,
        "price_history": build.tables.price_history,
        "probe_profiles": build.tables.probe_profiles,
        "online_route_log": build.tables.online_route_log,
    }
    written: list[WrittenCanonicalTable] = []
    for name, records in table_records.items():
        written_table = write_canonical_parquet(
            name=name,
            records=records,
            schema=schemas[name],
            path=output_root / f"{name}.parquet",
        )
        written.append(written_table)
        write_jsonl_debug(
            records,
            path=output_root / "debug" / f"{name}.jsonl",
            limit=debug_limit,
        )

    manifest_path = output_root / "canonical_manifest.json"
    output_manifest = {
        "manifest_version": 1,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "source_dataset": build.source_dataset,
        "source_revision": build.source_revision,
        "source_manifest_sha256": build.source_manifest_sha256,
        "debug_jsonl_limit": debug_limit,
        "temporal_metadata": {
            "available": False,
            "reason": "xRouteBench provides neither query timestamps nor model release dates",
        },
        "tables": [
            {
                **asdict(item),
                "path": item.path.relative_to(output_root).as_posix(),
            }
            for item in sorted(written, key=lambda value: value.name)
        ],
    }
    _write_json_atomic(manifest_path, output_manifest)
    return WrittenCanonicalDataset(
        root=output_root,
        manifest_path=manifest_path,
        tables=tuple(written),
    )
