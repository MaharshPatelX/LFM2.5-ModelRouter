"""Deterministic, value-preserving checks for the xRouteBench adapter."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from lfm_model_router.data.adapters.xroutebench import (
    XRouteBenchAdapter,
    XRouteBenchError,
    XRouteBenchField,
    XRouteBenchFile,
    XRouteBenchManifest,
    load_jsonl_records,
    load_xroutebench_manifest,
    load_xroutebench_schemas,
    sha256_file,
)

MANIFEST_PATH = Path("data/manifests/xroutebench.json")
SCHEMA_PATH = Path("data/manifests/xroutebench_schema.json")
FIXTURE_PATH = Path("data/fixtures/xroutebench/synthetic_routing_sample.jsonl")
PINNED_REVISION = "ea4b6e1b29d9a734f55f0a637baf326bad6aa681"


def test_manifest_is_pinned_and_has_every_split_file() -> None:
    manifest = load_xroutebench_manifest(MANIFEST_PATH)

    assert manifest.dataset_id == "ulab-ai/xRouteBench"
    assert manifest.revision == PINNED_REVISION
    assert len(manifest.files) == 41
    assert len({(item.config, item.split) for item in manifest.files}) == 41
    assert sum(item.size_bytes for item in manifest.files) == 47_382_959
    assert sum(item.rows for item in manifest.files) == 245_903


def test_schema_snapshot_covers_all_configs() -> None:
    manifest = load_xroutebench_manifest(MANIFEST_PATH)
    schemas = load_xroutebench_schemas(SCHEMA_PATH)

    assert len(schemas) == 17
    assert {item.config for item in manifest.files} == schemas.keys()
    assert tuple(field.name for field in schemas["llm_candidates"]) == (
        "model_name",
        "size",
        "input_price_per_1m",
        "output_price_per_1m",
        "service",
        "api_model_id",
        "description",
    )


def test_synthetic_fixture_loads_deterministically_without_coercion() -> None:
    first = load_jsonl_records(FIXTURE_PATH)
    second = load_jsonl_records(FIXTURE_PATH)

    assert first == second
    assert len(first) == 3
    assert first[0]["choices"] is None
    assert first[1]["task_id"] == "fixture-2"
    assert first[2]["response_time"] == 0.015


def test_manifest_rejects_unknown_config_split() -> None:
    manifest = load_xroutebench_manifest(MANIFEST_PATH)

    with pytest.raises(XRouteBenchError, match="unknown xRouteBench config/split"):
        manifest.file_for("does_not_exist", "train")


def _temporary_adapter(
    tmp_path: Path,
    *,
    records: list[dict[str, object]],
    fields: tuple[XRouteBenchField, ...],
) -> XRouteBenchAdapter:
    arrow = importlib.import_module("pyarrow")
    parquet = importlib.import_module("pyarrow.parquet")
    source_path = tmp_path / "synthetic" / "train.parquet"
    source_path.parent.mkdir(parents=True)
    parquet.write_table(arrow.Table.from_pylist(records), source_path)
    source_file = XRouteBenchFile(
        config="synthetic",
        split="train",
        path="synthetic/train.parquet",
        rows=len(records),
        columns=len(fields),
        size_bytes=source_path.stat().st_size,
        sha256=sha256_file(source_path),
    )
    manifest = XRouteBenchManifest(
        dataset_id="synthetic/xroutebench",
        revision="0" * 40,
        schema_snapshot="schema.json",
        resolve_base_url="https://example.invalid/",
        files=(source_file,),
    )
    return XRouteBenchAdapter(
        data_root=tmp_path,
        manifest=manifest,
        schemas={"synthetic": fields},
    )


def test_parquet_adapter_preserves_values_and_nulls(tmp_path: Path) -> None:
    records: list[dict[str, object]] = [
        {"task_name": "alpha", "choices": ["A", "B"], "score": 1.0},
        {"task_name": "beta", "choices": None, "score": 0.0},
    ]
    fields = (
        XRouteBenchField("task_name", "string"),
        XRouteBenchField("choices", "list[string]"),
        XRouteBenchField("score", "float64"),
    )
    adapter = _temporary_adapter(tmp_path, records=records, fields=fields)

    first = tuple(adapter.iter_split("synthetic", "train", batch_size=1))
    second = tuple(adapter.iter_split("synthetic", "train", batch_size=2))

    assert first == second == tuple(records)


def test_parquet_adapter_rejects_schema_drift(tmp_path: Path) -> None:
    records: list[dict[str, object]] = [{"task_name": "alpha", "score": 1.0}]
    incorrect_fields = (
        XRouteBenchField("task_name", "string"),
        XRouteBenchField("renamed_score", "float64"),
    )
    adapter = _temporary_adapter(tmp_path, records=records, fields=incorrect_fields)

    with pytest.raises(XRouteBenchError, match="column mismatch"):
        tuple(adapter.iter_split("synthetic", "train"))


def test_parquet_adapter_rejects_integrity_drift(tmp_path: Path) -> None:
    records: list[dict[str, object]] = [{"task_name": "alpha"}]
    fields = (XRouteBenchField("task_name", "string"),)
    adapter = _temporary_adapter(tmp_path, records=records, fields=fields)
    source = adapter.local_path("synthetic", "train")
    source.write_bytes(source.read_bytes() + b"drift")

    with pytest.raises(XRouteBenchError, match="size mismatch"):
        tuple(adapter.iter_split("synthetic", "train"))
