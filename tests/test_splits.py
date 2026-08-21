"""Reproducibility and leakage-boundary proofs for all Part 4 strategies."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import cast

import pytest

from lfm_model_router.data.deduplication import deduplicate_queries
from lfm_model_router.data.splits import (
    SPLIT_STRATEGIES,
    EntityPartitions,
    ModelForSplitting,
    SplitBuildConfig,
    SplitError,
    SplitValidationError,
    build_all_split_manifests,
    build_split_manifest,
    validate_split_manifest,
)
from tests.part4_test_data import make_models, make_queries


def _config(*, seed: int = 3407) -> SplitBuildConfig:
    return SplitBuildConfig(
        dataset_id="synthetic/xroutebench",
        dataset_revision="revision-for-tests",
        canonical_schema_version="canonical-v1",
        seed=seed,
    )


def test_same_seed_recreates_all_six_manifests_byte_for_byte() -> None:
    queries = make_queries()
    models = make_models()
    deduplication = deduplicate_queries(queries)

    first = build_all_split_manifests(
        queries=queries,
        models=models,
        deduplication=deduplication,
        config=_config(),
    )
    second = build_all_split_manifests(
        queries=tuple(reversed(queries)),
        models=tuple(reversed(models)),
        deduplication=deduplicate_queries(tuple(reversed(queries))),
        config=_config(),
    )

    assert set(first) == set(SPLIT_STRATEGIES)
    assert {name: value.to_json() for name, value in first.items()} == {
        name: value.to_json() for name, value in second.items()
    }


def test_different_seed_changes_randomized_prompt_split() -> None:
    queries = make_queries()
    models = make_models()
    deduplication = deduplicate_queries(queries)

    first = build_split_manifest(
        "prompt_iid",
        queries=queries,
        models=models,
        deduplication=deduplication,
        config=_config(seed=1),
    )
    second = build_split_manifest(
        "prompt_iid",
        queries=queries,
        models=models,
        deduplication=deduplication,
        config=_config(seed=2),
    )

    assert first.queries != second.queries


def test_duplicate_and_probe_clusters_never_cross_query_boundaries() -> None:
    queries = make_queries()
    models = make_models()
    deduplication = deduplicate_queries(queries)
    manifests = build_all_split_manifests(
        queries=queries,
        models=models,
        deduplication=deduplication,
        config=_config(),
    )

    for manifest in manifests.values():
        memberships = manifest.queries.named()
        for cluster in deduplication.clusters:
            occupied = {
                name
                for name, members in memberships.items()
                if set(cluster.query_ids) & set(members)
            }
            assert len(occupied) == 1
        assert set(manifest.queries.probe) == {"probe-00", "probe-copy"}
        assert not set(manifest.queries.probe) & set(manifest.queries.test)


def test_task_family_model_and_joint_boundaries_are_explicit() -> None:
    queries = make_queries()
    models = make_models()
    deduplication = deduplicate_queries(queries)
    manifests = build_all_split_manifests(
        queries=queries,
        models=models,
        deduplication=deduplication,
        config=_config(),
    )

    assert manifests["task_held_out"].held_out_tasks
    assert manifests["model_held_out"].held_out_models
    assert manifests["family_held_out"].held_out_families
    assert manifests["joint_new_model_new_task"].held_out_tasks
    assert manifests["joint_new_model_new_task"].held_out_models
    assert manifests["model_held_out"].model_identities[0].aliases == (
        "api/model-00",
        "MODEL ALIAS 00",
        "model-00",
    )

    model_by_id = {model.model_id: model for model in models}
    family_manifest = manifests["family_held_out"]
    family_memberships: dict[str, set[str]] = {}
    for split_name in ("train", "validation", "test"):
        for model_id in getattr(family_manifest.models, split_name):
            model = model_by_id[model_id]
            family_memberships.setdefault(model.family, set()).add(split_name)
    assert all(len(memberships) == 1 for memberships in family_memberships.values())


def test_temporal_split_is_chronological_for_queries_and_models() -> None:
    queries = make_queries()
    models = make_models()
    manifest = build_split_manifest(
        "temporal",
        queries=queries,
        models=models,
        deduplication=deduplicate_queries(queries),
        config=_config(),
    )
    query_by_id = {query.query_id: query for query in queries}
    model_by_id = {model.model_id: model for model in models}

    assert max(
        cast(datetime, query_by_id[item].observed_at) for item in manifest.queries.train
    ) <= min(cast(datetime, query_by_id[item].observed_at) for item in manifest.queries.validation)
    assert max(
        cast(datetime, query_by_id[item].observed_at) for item in manifest.queries.validation
    ) <= min(cast(datetime, query_by_id[item].observed_at) for item in manifest.queries.test)
    assert max(
        cast(datetime, model_by_id[item].available_at) for item in manifest.models.train
    ) <= min(cast(datetime, model_by_id[item].available_at) for item in manifest.models.validation)
    assert manifest.temporal_query_boundaries
    assert manifest.temporal_model_boundaries


def test_temporal_split_rejects_missing_dates() -> None:
    queries = make_queries()
    models = list(make_models())
    models[0] = replace(models[0], available_at=None)

    with pytest.raises(SplitError, match="available_at"):
        build_split_manifest(
            "temporal",
            queries=queries,
            models=tuple(models),
            deduplication=deduplicate_queries(queries),
            config=_config(),
        )


def test_alias_collision_is_rejected() -> None:
    queries = make_queries()
    models = list(make_models())
    models[1] = replace(models[1], aliases=(*models[1].aliases, " model alias 00 "))

    with pytest.raises(SplitError, match="maps to both"):
        build_split_manifest(
            "model_held_out",
            queries=queries,
            models=tuple(models),
            deduplication=deduplicate_queries(queries),
            config=_config(),
        )


def test_equivalent_aliases_have_a_stable_tie_break() -> None:
    queries = make_queries()
    models = list(make_models())
    models[0] = replace(models[0], aliases=(*models[0].aliases, " MODEL ALIAS 00 "))

    manifest = build_split_manifest(
        "model_held_out",
        queries=queries,
        models=tuple(models),
        deduplication=deduplicate_queries(queries),
        config=_config(),
    )

    identity = next(
        value for value in manifest.model_identities if value.model_id == models[0].model_id
    )
    assert identity.aliases.index(" MODEL ALIAS 00 ") < identity.aliases.index("MODEL ALIAS 00")


def test_validator_detects_a_duplicate_moved_into_test() -> None:
    queries = make_queries()
    models = make_models()
    deduplication = deduplicate_queries(queries)
    manifest = build_split_manifest(
        "prompt_iid",
        queries=queries,
        models=models,
        deduplication=deduplication,
        config=_config(),
    )
    cluster = next(cluster for cluster in deduplication.clusters if len(cluster.query_ids) > 1)
    first, second = cluster.query_ids[:2]
    original_partition = next(
        name for name in ("train", "validation", "test") if first in getattr(manifest.queries, name)
    )
    target_partition = "train" if original_partition == "test" else "test"
    values = {
        name: tuple(item for item in getattr(manifest.queries, name) if item != second)
        for name in ("train", "validation", "test")
    }
    values[target_partition] = tuple(sorted((*values[target_partition], second)))
    tampered = replace(
        manifest,
        queries=EntityPartitions(
            train=values["train"],
            validation=values["validation"],
            test=values["test"],
            probe=manifest.queries.probe,
        ),
    )

    with pytest.raises(SplitValidationError, match="duplicate cluster"):
        validate_split_manifest(
            tampered,
            queries=queries,
            models=models,
            deduplication=deduplication,
        )


def test_model_timestamp_type_is_timezone_aware() -> None:
    model = ModelForSplitting(
        model_id="model",
        provider="provider",
        family="family",
        version="version",
        available_at=datetime(2025, 1, 1),
    )
    models = (model, *make_models()[:2])
    queries = make_queries()

    with pytest.raises(SplitError, match="timezone"):
        build_split_manifest(
            "model_held_out",
            queries=queries,
            models=models,
            deduplication=deduplicate_queries(queries),
            config=_config(),
        )
