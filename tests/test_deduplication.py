"""Exact, normalized, identity, lineage, and near-duplicate checks."""

from __future__ import annotations

import pytest

from lfm_model_router.data.deduplication import (
    DeduplicationConfig,
    DeduplicationError,
    QueryForSplitting,
    deduplicate_queries,
    fingerprint_prompt,
    normalize_prompt,
)
from tests.part4_test_data import make_queries


def _cluster_for(query_id: str) -> set[str]:
    result = deduplicate_queries(make_queries())
    return set(
        next(cluster.query_ids for cluster in result.clusters if query_id in cluster.query_ids)
    )


def test_fingerprints_distinguish_exact_text_but_group_normalized_text() -> None:
    first = fingerprint_prompt(query_id="one", prompt="  Hello\nWORLD ")
    second = fingerprint_prompt(query_id="two", prompt="hello world")

    assert first.exact_sha256 != second.exact_sha256
    assert first.normalized_sha256 == second.normalized_sha256
    assert normalize_prompt("  Hello\nWORLD ") == "hello world"


def test_all_supported_duplicate_evidence_creates_atomic_clusters() -> None:
    assert {"q-00", "q-01"} <= _cluster_for("q-00")
    assert {"q-02", "q-03"} <= _cluster_for("q-02")
    assert {"q-04", "q-05"} <= _cluster_for("q-04")
    assert {"q-06", "q-07"} <= _cluster_for("q-06")
    assert {"q-08", "q-09"} <= _cluster_for("q-08")


def test_probe_near_copy_is_discoverable_for_probe_closure() -> None:
    assert _cluster_for("probe-00") == {"probe-00", "probe-copy"}


def test_deduplication_is_order_independent() -> None:
    queries = make_queries()

    first = deduplicate_queries(queries)
    second = deduplicate_queries(tuple(reversed(queries)))

    assert first.fingerprints == second.fingerprints
    assert first.clusters == second.clusters
    assert first.near_duplicate_pairs == second.near_duplicate_pairs


def test_duplicate_query_ids_fail_understandably() -> None:
    query = QueryForSplitting(
        query_id="same",
        prompt="prompt",
        task="task",
        source="source",
    )

    with pytest.raises(DeduplicationError, match="duplicate query_id"):
        deduplicate_queries((query, query))


def test_invalid_near_duplicate_configuration_is_rejected() -> None:
    config = DeduplicationConfig(near_duplicate_threshold=0.0)

    with pytest.raises(DeduplicationError, match="threshold"):
        deduplicate_queries(make_queries(), config=config)
