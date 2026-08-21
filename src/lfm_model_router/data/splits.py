"""Reproducible, leakage-safe query and model split construction."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Final, Literal, cast

from lfm_model_router.data.deduplication import (
    DeduplicationResult,
    QueryForSplitting,
)

SplitName = Literal["train", "validation", "test"]
SplitStrategy = Literal[
    "prompt_iid",
    "task_held_out",
    "model_held_out",
    "family_held_out",
    "temporal",
    "joint_new_model_new_task",
]

SPLIT_NAMES: Final[tuple[SplitName, ...]] = ("train", "validation", "test")
SPLIT_STRATEGIES: Final[tuple[SplitStrategy, ...]] = (
    "prompt_iid",
    "task_held_out",
    "model_held_out",
    "family_held_out",
    "temporal",
    "joint_new_model_new_task",
)


class SplitError(ValueError):
    """Raised when leakage-safe splits cannot be constructed."""


class SplitValidationError(SplitError):
    """Raised when a generated split violates a leakage boundary."""


@dataclass(frozen=True, slots=True)
class ModelForSplitting:
    """The canonical model fields needed to enforce held-out boundaries."""

    model_id: str
    provider: str
    family: str
    version: str
    aliases: tuple[str, ...] = ()
    available_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SplitRatios:
    """Train, validation, and test proportions."""

    train: float = 0.80
    validation: float = 0.10
    test: float = 0.10

    def validate(self) -> None:
        """Require positive ratios that sum to one."""
        values = (self.train, self.validation, self.test)
        if any(value <= 0.0 for value in values):
            raise SplitError("all split ratios must be positive")
        if abs(sum(values) - 1.0) > 1e-9:
            raise SplitError("split ratios must sum to 1.0")

    def as_dict(self) -> dict[SplitName, float]:
        """Return ratios with stable split names."""
        return {
            "train": self.train,
            "validation": self.validation,
            "test": self.test,
        }


@dataclass(frozen=True, slots=True)
class SplitBuildConfig:
    """Dataset identity and deterministic split controls."""

    dataset_id: str
    dataset_revision: str
    canonical_schema_version: str
    seed: int = 3407
    ratios: SplitRatios = SplitRatios()
    manifest_version: str = "1.0.0"
    algorithm_version: str = "leakage-safe-splits-v1"

    def validate(self) -> None:
        """Reject incomplete provenance and invalid random-state settings."""
        for field, value in (
            ("dataset_id", self.dataset_id),
            ("dataset_revision", self.dataset_revision),
            ("canonical_schema_version", self.canonical_schema_version),
            ("manifest_version", self.manifest_version),
            ("algorithm_version", self.algorithm_version),
        ):
            if not value.strip():
                raise SplitError(f"{field} must not be empty")
        if self.seed < 0:
            raise SplitError("seed must be non-negative")
        self.ratios.validate()


@dataclass(frozen=True, slots=True)
class EntityPartitions:
    """Explicit memberships for one query or model split dimension."""

    train: tuple[str, ...] = ()
    validation: tuple[str, ...] = ()
    test: tuple[str, ...] = ()
    probe: tuple[str, ...] = ()
    shared: tuple[str, ...] = ()

    def named(self) -> dict[str, tuple[str, ...]]:
        """Return every partition in a stable order."""
        return {
            "train": self.train,
            "validation": self.validation,
            "test": self.test,
            "probe": self.probe,
            "shared": self.shared,
        }


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Canonical family and alias information embedded in every split manifest."""

    model_id: str
    provider: str
    family: str
    version: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SplitManifest:
    """One versioned split definition with complete provenance."""

    manifest_version: str
    algorithm_version: str
    strategy: SplitStrategy
    dataset_id: str
    dataset_revision: str
    canonical_schema_version: str
    seed: int
    ratios: SplitRatios
    source_digest: str
    deduplication_digest: str
    queries: EntityPartitions
    models: EntityPartitions
    model_identities: tuple[ModelIdentity, ...]
    held_out_tasks: tuple[str, ...] = ()
    held_out_models: tuple[str, ...] = ()
    held_out_families: tuple[str, ...] = ()
    temporal_query_boundaries: tuple[str, ...] = ()
    temporal_model_boundaries: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation with deterministic list ordering."""
        return cast(dict[str, object], asdict(self))

    def to_json(self) -> str:
        """Serialize byte-for-byte reproducibly."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parents = list(range(size))

    def find(self, item: int) -> int:
        parent = self._parents[item]
        if parent != item:
            self._parents[item] = self.find(parent)
        return self._parents[item]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self._parents[right_root] = left_root


def _stable_hash(*values: object) -> str:
    joined = "\x1f".join(str(value) for value in values)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _normalize_alias(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _alias_sort_key(value: str) -> tuple[str, str]:
    """Order aliases deterministically even when normalization makes them equal."""
    return (_normalize_alias(value), value)


def _validate_models(models: tuple[ModelForSplitting, ...]) -> dict[str, str]:
    if not models:
        raise SplitError("at least one model is required")
    seen_ids: set[str] = set()
    alias_to_model: dict[str, str] = {}
    for index, model in enumerate(models):
        for field, value in (
            ("model_id", model.model_id),
            ("provider", model.provider),
            ("family", model.family),
            ("version", model.version),
        ):
            if not value.strip():
                raise SplitError(f"models[{index}].{field} must not be empty")
        if model.model_id in seen_ids:
            raise SplitError(f"duplicate model_id: {model.model_id}")
        seen_ids.add(model.model_id)
        if model.available_at is not None and model.available_at.tzinfo is None:
            raise SplitError(f"model {model.model_id} available_at must include a timezone")
        for alias in (model.model_id, *model.aliases):
            normalized = _normalize_alias(alias)
            if not normalized:
                raise SplitError(f"model {model.model_id} contains an empty alias")
            owner = alias_to_model.get(normalized)
            if owner is not None and owner != model.model_id:
                raise SplitError(
                    f"model alias {alias!r} maps to both {owner!r} and {model.model_id!r}"
                )
            alias_to_model[normalized] = model.model_id
    return alias_to_model


def _model_identities(models: tuple[ModelForSplitting, ...]) -> tuple[ModelIdentity, ...]:
    return tuple(
        ModelIdentity(
            model_id=model.model_id,
            provider=model.provider,
            family=model.family,
            version=model.version,
            aliases=tuple(
                sorted(
                    {model.model_id, *model.aliases},
                    key=_alias_sort_key,
                )
            ),
        )
        for model in sorted(models, key=lambda item: item.model_id)
    )


def _source_digest(
    queries: tuple[QueryForSplitting, ...], models: tuple[ModelForSplitting, ...]
) -> str:
    query_values = [
        {
            "query_id": query.query_id,
            "prompt_sha256": _stable_hash(query.prompt),
            "task": query.task,
            "source": query.source,
            "source_query_id": query.source_query_id,
            "lineage_id": query.lineage_id,
            "observed_at": query.observed_at.isoformat() if query.observed_at else None,
            "is_probe": query.is_probe,
        }
        for query in sorted(queries, key=lambda item: item.query_id)
    ]
    model_values = [
        {
            "model_id": model.model_id,
            "provider": model.provider,
            "family": model.family,
            "version": model.version,
            "aliases": sorted(model.aliases),
            "available_at": model.available_at.isoformat() if model.available_at else None,
        }
        for model in sorted(models, key=lambda item: item.model_id)
    ]
    payload = json.dumps(
        {"queries": query_values, "models": model_values},
        separators=(",", ":"),
        sort_keys=True,
    )
    return _stable_hash(payload)


def deduplication_digest(result: DeduplicationResult) -> str:
    """Hash the common deduplication artifact referenced by split manifests."""
    payload = {
        "config": asdict(result.config),
        "fingerprints": [asdict(value) for value in result.fingerprints],
        "clusters": [asdict(value) for value in result.clusters],
        "near_duplicate_pairs": result.near_duplicate_pairs,
        "skipped_near_duplicate_buckets": result.skipped_near_duplicate_buckets,
    }
    return _stable_hash(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _query_probe_ids(
    queries: tuple[QueryForSplitting, ...], deduplication: DeduplicationResult
) -> set[str]:
    explicit_probes = {query.query_id for query in queries if query.is_probe}
    return {
        query_id
        for cluster in deduplication.clusters
        if explicit_probes & set(cluster.query_ids)
        for query_id in cluster.query_ids
    }


def _atomic_query_groups(
    queries: tuple[QueryForSplitting, ...],
    *,
    deduplication: DeduplicationResult,
    probe_ids: set[str],
    group_by_task: bool,
    group_by_time: bool,
) -> dict[str, tuple[str, ...]]:
    eligible = tuple(query for query in queries if query.query_id not in probe_ids)
    if len(eligible) < len(SPLIT_NAMES):
        raise SplitError("at least three non-probe queries are required")
    index_by_id = {query.query_id: index for index, query in enumerate(eligible)}
    union_find = _UnionFind(len(eligible))

    for cluster in deduplication.clusters:
        members = [
            index_by_id[query_id] for query_id in cluster.query_ids if query_id in index_by_id
        ]
        for member in members[1:]:
            union_find.union(members[0], member)

    def union_values(values: list[tuple[object, int]]) -> None:
        grouped: dict[object, list[int]] = defaultdict(list)
        for value, index in values:
            grouped[value].append(index)
        for members in grouped.values():
            for member in members[1:]:
                union_find.union(members[0], member)

    if group_by_task:
        union_values([(query.task, index) for index, query in enumerate(eligible)])
    if group_by_time:
        missing = [query.query_id for query in eligible if query.observed_at is None]
        if missing:
            raise SplitError(
                "temporal split requires observed_at for every non-probe query; "
                f"missing {len(missing)} value(s)"
            )
        union_values([(query.observed_at, index) for index, query in enumerate(eligible)])

    members_by_root: dict[int, list[str]] = defaultdict(list)
    for index, query in enumerate(eligible):
        members_by_root[union_find.find(index)].append(query.query_id)
    return {
        f"query-group-{_stable_hash(*sorted(members))[:20]}": tuple(sorted(members))
        for members in members_by_root.values()
    }


def _partition_groups_randomly(
    groups: dict[str, tuple[str, ...]], *, seed: int, ratios: SplitRatios, namespace: str
) -> dict[SplitName, tuple[str, ...]]:
    ordered = sorted(groups.items(), key=lambda item: _stable_hash(seed, namespace, item[0]))
    if len(ordered) < len(SPLIT_NAMES):
        raise SplitError(
            f"{namespace} has only {len(ordered)} atomic group(s); at least three are required"
        )
    total_members = sum(len(members) for _, members in ordered)
    train_boundary = ratios.train * total_members
    validation_boundary = (ratios.train + ratios.validation) * total_members
    partitions: dict[SplitName, list[str]] = {name: [] for name in SPLIT_NAMES}
    consumed = 0
    for index, (_, members) in enumerate(ordered):
        empty_splits = [name for name in SPLIT_NAMES if not partitions[name]]
        remaining_groups = len(ordered) - index
        midpoint = consumed + len(members) / 2
        split: SplitName
        if remaining_groups == len(empty_splits):
            split = empty_splits[0]
        elif midpoint <= train_boundary:
            split = "train"
        elif midpoint <= validation_boundary:
            split = "validation"
        else:
            split = "test"
        partitions[split].extend(members)
        consumed += len(members)
    _require_nonempty(partitions, entity=namespace)
    return {name: tuple(sorted(partitions[name])) for name in SPLIT_NAMES}


def _partition_groups_temporally(
    groups: dict[str, tuple[str, ...]],
    *,
    timestamps: dict[str, datetime],
    ratios: SplitRatios,
    entity: str,
) -> tuple[dict[SplitName, tuple[str, ...]], tuple[str, ...]]:
    ordered = sorted(
        groups.items(),
        key=lambda item: (max(timestamps[member] for member in item[1]), item[0]),
    )
    if len(ordered) < len(SPLIT_NAMES):
        raise SplitError(
            f"{entity} has only {len(ordered)} temporal group(s); at least three are required"
        )
    total_members = sum(len(members) for _, members in ordered)
    train_boundary = ratios.train * total_members
    validation_boundary = (ratios.train + ratios.validation) * total_members
    partitions: dict[SplitName, list[str]] = {name: [] for name in SPLIT_NAMES}
    consumed = 0
    for index, (_, members) in enumerate(ordered):
        empty_splits = [name for name in SPLIT_NAMES if not partitions[name]]
        remaining_groups = len(ordered) - index
        midpoint = consumed + len(members) / 2
        split: SplitName
        if remaining_groups == len(empty_splits):
            split = empty_splits[0]
        elif midpoint <= train_boundary:
            split = "train"
        elif midpoint <= validation_boundary:
            split = "validation"
        else:
            split = "test"
        partitions[split].extend(members)
        consumed += len(members)
    _require_nonempty(partitions, entity=entity)
    result = {name: tuple(sorted(partitions[name])) for name in SPLIT_NAMES}
    boundaries = (
        max(timestamps[item] for item in result["train"]).isoformat(),
        max(timestamps[item] for item in result["validation"]).isoformat(),
    )
    return result, boundaries


def _require_nonempty(partitions: dict[SplitName, list[str]], *, entity: str) -> None:
    empty = [name for name in SPLIT_NAMES if not partitions[name]]
    if empty:
        raise SplitError(
            f"{entity} split produced empty partition(s) {empty}; provide more atomic groups "
            "or adjust split ratios"
        )


def _model_groups(
    models: tuple[ModelForSplitting, ...], *, group_by_family: bool, group_by_time: bool
) -> dict[str, tuple[str, ...]]:
    grouped: dict[object, list[str]] = defaultdict(list)
    for model in models:
        if group_by_time:
            if model.available_at is None:
                raise SplitError(
                    "temporal split requires available_at for every model; "
                    f"missing value for {model.model_id}"
                )
            key: object = model.available_at
        elif group_by_family:
            key = model.family.casefold()
        else:
            key = model.model_id
        grouped[key].append(model.model_id)
    return {
        f"model-group-{_stable_hash(*sorted(members))[:20]}": tuple(sorted(members))
        for members in grouped.values()
    }


def _entity_partitions(
    values: dict[SplitName, tuple[str, ...]], *, probe: tuple[str, ...] = ()
) -> EntityPartitions:
    return EntityPartitions(
        train=values["train"],
        validation=values["validation"],
        test=values["test"],
        probe=probe,
    )


def build_split_manifest(
    strategy: SplitStrategy,
    *,
    queries: tuple[QueryForSplitting, ...],
    models: tuple[ModelForSplitting, ...],
    deduplication: DeduplicationResult,
    config: SplitBuildConfig,
) -> SplitManifest:
    """Build and validate one independent leakage-safe split strategy."""
    if strategy not in SPLIT_STRATEGIES:
        raise SplitError(f"unknown split strategy: {strategy}")
    config.validate()
    _validate_models(models)
    query_ids = {query.query_id for query in queries}
    deduplicated_ids = {
        query_id for cluster in deduplication.clusters for query_id in cluster.query_ids
    }
    if query_ids != deduplicated_ids:
        raise SplitError("deduplication result does not cover exactly the supplied queries")

    probe_ids = _query_probe_ids(queries, deduplication)
    query_group_by_task = strategy in ("task_held_out", "joint_new_model_new_task")
    query_group_by_time = strategy == "temporal"
    query_groups = _atomic_query_groups(
        queries,
        deduplication=deduplication,
        probe_ids=probe_ids,
        group_by_task=query_group_by_task,
        group_by_time=query_group_by_time,
    )

    temporal_query_boundaries: tuple[str, ...] = ()
    if strategy == "temporal":
        query_timestamps = {
            query.query_id: cast(datetime, query.observed_at)
            for query in queries
            if query.query_id not in probe_ids
        }
        query_values, temporal_query_boundaries = _partition_groups_temporally(
            query_groups,
            timestamps=query_timestamps,
            ratios=config.ratios,
            entity="query",
        )
    else:
        query_values = _partition_groups_randomly(
            query_groups,
            seed=config.seed,
            ratios=config.ratios,
            namespace=f"{strategy}:queries",
        )
    query_partitions = _entity_partitions(query_values, probe=tuple(sorted(probe_ids)))

    model_split_required = strategy in (
        "model_held_out",
        "family_held_out",
        "temporal",
        "joint_new_model_new_task",
    )
    temporal_model_boundaries: tuple[str, ...] = ()
    if model_split_required:
        model_groups = _model_groups(
            models,
            group_by_family=strategy == "family_held_out",
            group_by_time=strategy == "temporal",
        )
        if strategy == "temporal":
            model_timestamps = {
                model.model_id: cast(datetime, model.available_at) for model in models
            }
            model_values, temporal_model_boundaries = _partition_groups_temporally(
                model_groups,
                timestamps=model_timestamps,
                ratios=config.ratios,
                entity="model",
            )
        else:
            model_values = _partition_groups_randomly(
                model_groups,
                seed=config.seed,
                ratios=config.ratios,
                namespace=f"{strategy}:models",
            )
        model_partitions = _entity_partitions(model_values)
    else:
        model_partitions = EntityPartitions(
            shared=tuple(sorted(model.model_id for model in models))
        )

    query_by_id = {query.query_id: query for query in queries}
    model_by_id = {model.model_id: model for model in models}
    model_identities = _model_identities(models)
    held_out_tasks = (
        tuple(sorted({query_by_id[item].task for item in query_partitions.test}))
        if query_group_by_task
        else ()
    )
    held_out_models = model_partitions.test if model_split_required else ()
    held_out_families = (
        tuple(sorted({model_by_id[item].family for item in model_partitions.test}))
        if strategy == "family_held_out"
        else ()
    )

    manifest = SplitManifest(
        manifest_version=config.manifest_version,
        algorithm_version=config.algorithm_version,
        strategy=strategy,
        dataset_id=config.dataset_id,
        dataset_revision=config.dataset_revision,
        canonical_schema_version=config.canonical_schema_version,
        seed=config.seed,
        ratios=config.ratios,
        source_digest=_source_digest(queries, models),
        deduplication_digest=deduplication_digest(deduplication),
        queries=query_partitions,
        models=model_partitions,
        model_identities=model_identities,
        held_out_tasks=held_out_tasks,
        held_out_models=held_out_models,
        held_out_families=held_out_families,
        temporal_query_boundaries=temporal_query_boundaries,
        temporal_model_boundaries=temporal_model_boundaries,
    )
    validate_split_manifest(
        manifest,
        queries=queries,
        models=models,
        deduplication=deduplication,
    )
    return manifest


def build_all_split_manifests(
    *,
    queries: tuple[QueryForSplitting, ...],
    models: tuple[ModelForSplitting, ...],
    deduplication: DeduplicationResult,
    config: SplitBuildConfig,
) -> dict[SplitStrategy, SplitManifest]:
    """Build all six required Part 4 split definitions."""
    return {
        strategy: build_split_manifest(
            strategy,
            queries=queries,
            models=models,
            deduplication=deduplication,
            config=config,
        )
        for strategy in SPLIT_STRATEGIES
    }


def _partition_lookup(partitions: EntityPartitions) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for name, members in partitions.named().items():
        for member in members:
            previous = lookup.get(member)
            if previous is not None:
                raise SplitValidationError(
                    f"entity {member!r} appears in both {previous!r} and {name!r}"
                )
            lookup[member] = name
    return lookup


def validate_split_manifest(
    manifest: SplitManifest,
    *,
    queries: tuple[QueryForSplitting, ...],
    models: tuple[ModelForSplitting, ...],
    deduplication: DeduplicationResult,
) -> None:
    """Prove the required query, duplicate, probe, alias, family, and time boundaries."""
    alias_to_model = _validate_models(models)
    query_lookup = _partition_lookup(manifest.queries)
    model_lookup = _partition_lookup(manifest.models)
    expected_query_ids = {query.query_id for query in queries}
    expected_model_ids = {model.model_id for model in models}
    if manifest.source_digest != _source_digest(queries, models):
        raise SplitValidationError("source digest does not match the supplied canonical inputs")
    if manifest.deduplication_digest != deduplication_digest(deduplication):
        raise SplitValidationError(
            "deduplication digest does not match the supplied duplicate clusters"
        )
    if set(query_lookup) != expected_query_ids:
        raise SplitValidationError("query partitions do not cover exactly the input query IDs")
    if set(model_lookup) != expected_model_ids:
        raise SplitValidationError("model partitions do not cover exactly the input model IDs")
    if manifest.model_identities != _model_identities(models):
        raise SplitValidationError(
            "model identity mapping does not exactly match the canonical model registry"
        )
    if manifest.queries.shared:
        raise SplitValidationError("queries must never use the shared model-only partition")
    if manifest.models.probe:
        raise SplitValidationError("models must never use the query-only probe partition")
    if any(not getattr(manifest.queries, name) for name in SPLIT_NAMES):
        raise SplitValidationError("train, validation, and test query partitions must be non-empty")

    model_split_required = manifest.strategy in (
        "model_held_out",
        "family_held_out",
        "temporal",
        "joint_new_model_new_task",
    )
    if model_split_required:
        if manifest.models.shared:
            raise SplitValidationError("held-out model strategies cannot use shared models")
        if any(not getattr(manifest.models, name) for name in SPLIT_NAMES):
            raise SplitValidationError(
                "held-out model strategies require non-empty train, validation, and test models"
            )
        if manifest.held_out_models != manifest.models.test:
            raise SplitValidationError("held_out_models must exactly match the test models")
    elif (
        manifest.models.train
        or manifest.models.validation
        or manifest.models.test
        or set(manifest.models.shared) != expected_model_ids
    ):
        raise SplitValidationError(
            "query-only strategies must expose every model only through the shared partition"
        )
    elif manifest.held_out_models:
        raise SplitValidationError("held_out_models is set for a strategy without model holdout")

    for cluster in deduplication.clusters:
        partitions = {query_lookup[query_id] for query_id in cluster.query_ids}
        if len(partitions) != 1:
            raise SplitValidationError(
                f"duplicate cluster {cluster.cluster_id} crosses query partitions: {partitions}"
            )

    expected_probe_ids = _query_probe_ids(queries, deduplication)
    if set(manifest.queries.probe) != expected_probe_ids:
        raise SplitValidationError(
            "probe partition must contain exactly the explicit probes and their duplicates"
        )
    if set(manifest.queries.probe) & set(manifest.queries.test):
        raise SplitValidationError("probe queries appear in final test traffic")

    if manifest.strategy in ("task_held_out", "joint_new_model_new_task"):
        task_partitions: dict[str, set[str]] = defaultdict(set)
        query_by_id = {query.query_id: query for query in queries}
        for query_id in (
            *manifest.queries.train,
            *manifest.queries.validation,
            *manifest.queries.test,
        ):
            task_partitions[query_by_id[query_id].task].add(query_lookup[query_id])
        leaked_tasks = [task for task, partitions in task_partitions.items() if len(partitions) > 1]
        if leaked_tasks:
            raise SplitValidationError(f"tasks cross held-out boundaries: {leaked_tasks}")
        expected_held_out_tasks = tuple(
            sorted({query_by_id[query_id].task for query_id in manifest.queries.test})
        )
        if manifest.held_out_tasks != expected_held_out_tasks:
            raise SplitValidationError("held_out_tasks does not match the test query tasks")
    elif manifest.held_out_tasks:
        raise SplitValidationError("held_out_tasks is set for a strategy without task holdout")

    if manifest.strategy == "family_held_out":
        family_partitions: dict[str, set[str]] = defaultdict(set)
        for model in models:
            family = model.family.casefold()
            family_partitions[family].add(model_lookup[model.model_id])
        leaked_families = [
            family for family, partitions in family_partitions.items() if len(partitions) > 1
        ]
        if leaked_families:
            raise SplitValidationError(
                f"model families cross held-out boundaries: {leaked_families}"
            )
        expected_held_out_families = tuple(
            sorted({model.family for model in models if model.model_id in manifest.models.test})
        )
        if manifest.held_out_families != expected_held_out_families:
            raise SplitValidationError("held_out_families does not match the test model families")
    elif manifest.held_out_families:
        raise SplitValidationError("held_out_families is set for a strategy without family holdout")

    for alias_owner in alias_to_model.values():
        if alias_owner not in model_lookup:
            raise SplitValidationError(
                f"alias owner is missing from model partitions: {alias_owner}"
            )

    if manifest.strategy == "temporal":
        query_by_id = {query.query_id: query for query in queries}
        model_by_id = {model.model_id: model for model in models}
        _validate_temporal_order(
            partitions=manifest.queries,
            timestamps={
                query_id: cast(datetime, query_by_id[query_id].observed_at)
                for query_id in query_lookup
                if query_lookup[query_id] != "probe"
            },
            entity="query",
        )
        _validate_temporal_order(
            partitions=manifest.models,
            timestamps={
                model_id: cast(datetime, model_by_id[model_id].available_at)
                for model_id in model_lookup
            },
            entity="model",
        )


def _validate_temporal_order(
    *, partitions: EntityPartitions, timestamps: dict[str, datetime], entity: str
) -> None:
    train_latest = max(timestamps[item] for item in partitions.train)
    validation_earliest = min(timestamps[item] for item in partitions.validation)
    validation_latest = max(timestamps[item] for item in partitions.validation)
    test_earliest = min(timestamps[item] for item in partitions.test)
    if train_latest > validation_earliest or validation_latest > test_earliest:
        raise SplitValidationError(f"{entity} temporal partitions are not chronological")
