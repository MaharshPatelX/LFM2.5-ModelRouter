"""Configuration and portable output checks for Part 4 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfm_model_router.data.canonical import canonical_schemas, write_canonical_parquet
from lfm_model_router.data.deduplication import deduplicate_queries
from lfm_model_router.data.split_io import (
    load_part4_config,
    load_split_models_jsonl,
    load_split_models_parquet,
    load_split_queries_jsonl,
    load_split_queries_parquet,
    write_split_bundle,
)
from lfm_model_router.data.splits import build_all_split_manifests
from lfm_model_router.storage import (
    STORAGE_ROOT_ENV,
    StorageConfigurationError,
    resolve_storage_root,
    storage_root_from_environment,
    validate_data_path,
    validate_storage_root,
)
from tests.part4_test_data import make_models, make_queries
from tests.test_canonical import _tables


def test_part4_config_is_versioned_and_portable() -> None:
    config = load_part4_config(Path("configs/splits/xroutebench_v1.toml"))

    assert config.seed == 3407
    assert config.manifest_version == "1.0.0"
    assert config.deduplication.near_duplicate_threshold == 0.90
    assert config.storage_environment_variable == STORAGE_ROOT_ENV
    assert config.use_project_root_by_default is True


def test_storage_environment_must_be_present_and_absolute(tmp_path: Path) -> None:
    with pytest.raises(StorageConfigurationError, match="not set"):
        storage_root_from_environment(environment={})
    with pytest.raises(StorageConfigurationError, match="absolute"):
        storage_root_from_environment(environment={STORAGE_ROOT_ENV: "relative/path"})

    assert (
        storage_root_from_environment(environment={STORAGE_ROOT_ENV: str(tmp_path)})
        == tmp_path.resolve()
    )


def test_repository_root_is_default_but_code_subdirectories_are_rejected() -> None:
    repository = Path.cwd().resolve()

    assert (
        resolve_storage_root(
            repository_root=repository,
            environment={},
        )
        == repository
    )
    assert validate_storage_root(storage_root=repository, repository_root=repository) == repository
    assert (
        validate_data_path(path=repository / "data" / "raw", repository_root=repository)
        == repository / "data" / "raw"
    )
    with pytest.raises(StorageConfigurationError, match="outside"):
        validate_storage_root(
            storage_root=repository / "src",
            repository_root=repository,
        )
    with pytest.raises(StorageConfigurationError, match="beneath"):
        validate_data_path(path=repository / "src" / "data", repository_root=repository)


def test_environment_can_override_the_portable_default(tmp_path: Path) -> None:
    repository = (tmp_path / "fake-repository").resolve()
    external = (tmp_path / "fake-external-storage").resolve()

    assert (
        resolve_storage_root(
            repository_root=repository,
            environment={STORAGE_ROOT_ENV: str(external)},
        )
        == external
    )


def test_jsonl_exchange_loaders_validate_part3_debug_exports(tmp_path: Path) -> None:
    query_path = tmp_path / "queries.jsonl"
    model_path = tmp_path / "models.jsonl"
    query_path.write_text(
        json.dumps(
            {
                "query_id": "q-1",
                "prompt": "hello",
                "task": "qa",
                "source": "fixture",
                "observed_at": "2025-01-01T00:00:00Z",
                "is_probe": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    model_path.write_text(
        json.dumps(
            {
                "model_id": "m-1",
                "provider": "provider",
                "family": "family",
                "version": "v1",
                "aliases": ["alias"],
                "available_at": "2024-01-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    queries = load_split_queries_jsonl(query_path)
    models = load_split_models_jsonl(model_path)

    assert queries[0].observed_at is not None
    assert queries[0].observed_at.utcoffset() is not None
    assert models[0].aliases == ("alias",)


def test_parquet_loaders_consume_only_eligible_canonical_queries(tmp_path: Path) -> None:
    tables = _tables()
    ineligible = dict(tables.queries[0])
    ineligible["query_id"] = "query-without-outcomes"
    ineligible["has_outcomes"] = False
    schemas = canonical_schemas()
    query_path = tmp_path / "queries.parquet"
    model_path = tmp_path / "models.parquet"
    write_canonical_parquet(
        name="queries",
        records=(*tables.queries, ineligible),
        schema=schemas["queries"],
        path=query_path,
    )
    write_canonical_parquet(
        name="models",
        records=tables.models,
        schema=schemas["models"],
        path=model_path,
    )

    queries = load_split_queries_parquet(query_path)
    models = load_split_models_parquet(model_path)

    assert tuple(query.query_id for query in queries) == ("query-1",)
    assert queries[0].source == "synthetic/source:queries"
    assert models[0].aliases == ("model-one", "provider/model-one")


def test_complete_bundle_is_written_to_ignored_project_data(tmp_path: Path) -> None:
    queries = make_queries()
    models = make_models()
    deduplication = deduplicate_queries(queries)
    part4 = load_part4_config(Path("configs/splits/xroutebench_v1.toml"))
    config = part4.split_build_config(
        dataset_id="synthetic/xroutebench",
        dataset_revision="test-revision",
        canonical_schema_version="canonical-v1",
    )
    manifests = build_all_split_manifests(
        queries=queries,
        models=models,
        deduplication=deduplication,
        config=config,
    )

    first = write_split_bundle(
        storage_root=tmp_path,
        repository_root=tmp_path,
        config=config,
        deduplication=deduplication,
        manifests=manifests,
    )
    first_bytes = {path.name: path.read_bytes() for path in first.split_manifests}
    second = write_split_bundle(
        storage_root=tmp_path,
        repository_root=tmp_path,
        config=config,
        deduplication=deduplication,
        manifests=manifests,
    )

    assert len(second.split_manifests) == 6
    assert second.manifest_directory.is_relative_to(tmp_path / "data" / "processed" / "part4")
    assert first_bytes == {path.name: path.read_bytes() for path in second.split_manifests}
    assert second.deduplication_manifest.is_file()
    assert second.deduplication_report.is_file()
    report = second.deduplication_report.read_text(encoding="utf-8")
    assert "Behavioral anchor prompt" not in report
    assert "Probe clusters are isolated" in report


def test_bundle_records_an_honest_unsupported_temporal_strategy(tmp_path: Path) -> None:
    queries = make_queries()
    models = make_models()
    deduplication = deduplicate_queries(queries)
    part4 = load_part4_config(Path("configs/splits/xroutebench_v1.toml"))
    config = part4.split_build_config(
        dataset_id="synthetic/xroutebench",
        dataset_revision="test-revision",
        canonical_schema_version="canonical-v1",
    )
    manifests = build_all_split_manifests(
        queries=queries,
        models=models,
        deduplication=deduplication,
        config=config,
    )
    del manifests["temporal"]

    paths = write_split_bundle(
        storage_root=tmp_path,
        repository_root=tmp_path,
        config=config,
        deduplication=deduplication,
        manifests=manifests,
        unsupported={"temporal": "source timestamps are unavailable"},
    )

    assert len(paths.split_manifests) == 5
    assert len(paths.unsupported_manifests) == 1
    value = json.loads(paths.unsupported_manifests[0].read_text(encoding="utf-8"))
    assert value["strategy"] == "temporal"
    assert value["status"] == "unsupported"
