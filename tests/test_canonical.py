"""Canonical schema, relationship, persistence, and price-math tests."""

from __future__ import annotations

import importlib
import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lfm_model_router.data.canonical import (
    CANONICAL_SCHEMA_VERSION,
    CanonicalDataError,
    CanonicalTables,
    PriceRates,
    canonical_schemas,
    compute_cost_usd,
    validate_canonical_tables,
    write_canonical_parquet,
    write_jsonl_debug,
)


def _tables() -> CanonicalTables:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    query: dict[str, object] = {
        "query_id": "query-1",
        "source_dataset": "synthetic/source",
        "source_revision": "revision-1",
        "source_config": "queries",
        "source_split": "train",
        "source_row_index": 0,
        "source_query_id": "source-query-1",
        "prompt": "What is two plus two?",
        "task": "math",
        "ground_truth": "4",
        "ground_truth_json": '"4"',
        "metric": "em",
        "modality": "text",
        "choices_json": "null",
        "metadata_json": "{}",
        "raw_source_json": '{"query":"What is two plus two?"}',
        "has_outcomes": True,
        "is_probe": True,
        "observed_at": None,
    }
    model: dict[str, object] = {
        "model_id": "model-1",
        "canonical_name": "model-one",
        "provider": "provider",
        "developer": "developer",
        "family": "family-one",
        "version": "v1",
        "aliases": ["model-one", "provider/model-one"],
        "api_model_id": "provider/model-one",
        "size_label": "1B",
        "parameter_count_billions": 1.0,
        "capabilities": ["text"],
        "description": "Synthetic model",
        "source_revision": "revision-1",
        "metadata_json": "{}",
        "available_at": None,
    }
    outcome: dict[str, object] = {
        "outcome_id": "outcome-1",
        "query_id": "query-1",
        "model_id": "model-1",
        "source_config": "outcomes",
        "source_split": "train",
        "source_row_index": 0,
        "source_query_index": 0,
        "candidate_position": None,
        "metric": "em",
        "response": "4",
        "score": 1.0,
        "total_tokens": 3,
        "input_tokens": 2,
        "output_tokens": 1,
        "latency_seconds": 0.1,
        "succeeded": True,
        "failure_type": None,
        "metadata_json": "{}",
    }
    price: dict[str, object] = {
        "price_id": "price-1",
        "price_snapshot_id": "snapshot-1",
        "model_id": "model-1",
        "effective_at": now,
        "currency": "USD",
        "unit_tokens": 1_000_000,
        "input_per_unit": 1.0,
        "cached_input_per_unit": 0.5,
        "output_per_unit": 2.0,
        "source": "synthetic",
        "source_revision": "revision-1",
        "metadata_json": "{}",
    }
    probe: dict[str, object] = {
        "probe_profile_id": "probe-1",
        "probe_set_id": "probe-set-1",
        "query_id": "query-1",
        "model_id": "model-1",
        "outcome_id": "outcome-1",
        "score": 1.0,
        "input_tokens": 2,
        "output_tokens": 1,
        "latency_seconds": 0.1,
        "observed_at": now,
        "metadata_json": "{}",
    }
    route: dict[str, object] = {
        "route_id": "route-1",
        "query_id": "query-1",
        "event_time": now,
        "candidate_model_ids": ["model-1"],
        "selected_model_id": "model-1",
        "selection_probability": 1.0,
        "predicted_quality": 0.9,
        "predicted_output_tokens": 1.0,
        "predicted_latency_seconds": 0.1,
        "feedback_score": 1.0,
        "feedback_received_at": now,
        "metadata_json": "{}",
    }
    return CanonicalTables(
        queries=(query,),
        models=(model,),
        outcomes=(outcome,),
        price_history=(price,),
        probe_profiles=(probe,),
        online_route_log=(route,),
    )


def test_all_six_versioned_schemas_exist() -> None:
    schemas = canonical_schemas()

    assert set(schemas) == {
        "queries",
        "models",
        "outcomes",
        "price_history",
        "probe_profiles",
        "online_route_log",
    }
    for schema in schemas.values():
        assert schema.metadata[b"canonical_schema_version"] == CANONICAL_SCHEMA_VERSION.encode()


def test_valid_tables_pass_relationship_checks() -> None:
    validate_canonical_tables(_tables())


def test_unknown_model_reference_fails_understandably() -> None:
    tables = _tables()
    outcome = dict(tables.outcomes[0])
    outcome["model_id"] = "missing-model"

    with pytest.raises(CanonicalDataError, match="unknown model"):
        validate_canonical_tables(replace(tables, outcomes=(outcome,)))


def test_token_total_and_has_outcome_drift_are_rejected() -> None:
    tables = _tables()
    outcome = dict(tables.outcomes[0])
    outcome["total_tokens"] = 99
    with pytest.raises(CanonicalDataError, match="does not equal"):
        validate_canonical_tables(replace(tables, outcomes=(outcome,)))

    query = dict(tables.queries[0])
    query["has_outcomes"] = False
    with pytest.raises(CanonicalDataError, match="disagrees"):
        validate_canonical_tables(replace(tables, queries=(query,)))


def test_model_alias_collision_is_rejected() -> None:
    tables = _tables()
    second = dict(tables.models[0])
    second["model_id"] = "model-2"
    second["canonical_name"] = "model-two"
    second["aliases"] = [" MODEL-ONE "]

    with pytest.raises(CanonicalDataError, match="maps to both"):
        validate_canonical_tables(replace(tables, models=(*tables.models, second)))


def test_price_recomputation_changes_without_mutating_outcome() -> None:
    tables = _tables()
    original_outcome = deepcopy(tables.outcomes[0])
    first = compute_cost_usd(
        input_tokens=1_000,
        cached_input_tokens=200,
        output_tokens=500,
        rates=PriceRates(1.0, 0.5, 2.0),
    )
    second = compute_cost_usd(
        input_tokens=1_000,
        cached_input_tokens=200,
        output_tokens=500,
        rates=PriceRates(2.0, 1.0, 4.0),
    )

    assert first == pytest.approx(0.0019)
    assert second == pytest.approx(0.0038)
    assert second == pytest.approx(first * 2)
    assert tables.outcomes[0] == original_outcome


def test_cached_tokens_require_a_cached_price() -> None:
    with pytest.raises(CanonicalDataError, match="cached-input price"):
        compute_cost_usd(
            input_tokens=100,
            cached_input_tokens=50,
            output_tokens=20,
            rates=PriceRates(1.0, None, 2.0),
        )


def test_cost_rejects_non_integer_token_counts() -> None:
    with pytest.raises(CanonicalDataError, match="non-negative integer"):
        compute_cost_usd(
            input_tokens=1.5,  # type: ignore[arg-type]
            output_tokens=20,
            rates=PriceRates(1.0, None, 2.0),
        )


def test_probe_and_route_values_are_validated() -> None:
    tables = _tables()
    probe = dict(tables.probe_profiles[0])
    probe["score"] = 1.1
    with pytest.raises(CanonicalDataError, match=r"probe_profiles.*score"):
        validate_canonical_tables(replace(tables, probe_profiles=(probe,)))

    route = dict(tables.online_route_log[0])
    route["selection_probability"] = 0.0
    with pytest.raises(CanonicalDataError, match="greater than zero"):
        validate_canonical_tables(replace(tables, online_route_log=(route,)))


def test_parquet_and_bounded_jsonl_writers_preserve_schema(tmp_path: Path) -> None:
    parquet = importlib.import_module("pyarrow.parquet")
    tables = _tables()
    schemas = canonical_schemas()
    records = {
        "queries": tables.queries,
        "models": tables.models,
        "outcomes": tables.outcomes,
        "price_history": tables.price_history,
        "probe_profiles": tables.probe_profiles,
        "online_route_log": tables.online_route_log,
    }

    for name, values in records.items():
        path = tmp_path / f"{name}.parquet"
        written = write_canonical_parquet(
            name=name,
            records=values,
            schema=schemas[name],
            path=path,
        )
        assert written.rows == 1
        assert written.size_bytes > 0
        assert parquet.read_schema(path) == schemas[name]

    debug_path = tmp_path / "queries.jsonl"
    write_jsonl_debug(tables.queries, path=debug_path, limit=1)
    debug = json.loads(debug_path.read_text(encoding="utf-8"))
    assert debug["query_id"] == "query-1"
