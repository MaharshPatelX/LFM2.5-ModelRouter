"""Deterministic prompt fingerprinting and duplicate clustering."""

from __future__ import annotations

import hashlib
import itertools
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", flags=re.UNICODE)


class DeduplicationError(ValueError):
    """Raised when split inputs or deduplication settings are invalid."""


@dataclass(frozen=True, slots=True)
class QueryForSplitting:
    """The canonical query fields needed to create leakage-safe splits."""

    query_id: str
    prompt: str
    task: str
    source: str
    source_query_id: str | None = None
    lineage_id: str | None = None
    observed_at: datetime | None = None
    is_probe: bool = False


@dataclass(frozen=True, slots=True)
class DeduplicationConfig:
    """Versioned controls for deterministic near-duplicate discovery."""

    normalization_version: str = "nfkc-casefold-whitespace-v1"
    near_duplicate_threshold: float = 0.90
    shingle_size: int = 3
    signature_size: int = 8
    max_bucket_size: int = 128
    max_candidate_pairs: int = 1_000_000

    def validate(self) -> None:
        """Reject settings that would be undefined or unexpectedly expensive."""
        if self.normalization_version != "nfkc-casefold-whitespace-v1":
            raise DeduplicationError(
                f"unsupported normalization version: {self.normalization_version}"
            )
        if not 0.0 < self.near_duplicate_threshold <= 1.0:
            raise DeduplicationError("near_duplicate_threshold must be in (0, 1]")
        if self.shingle_size <= 0:
            raise DeduplicationError("shingle_size must be positive")
        if self.signature_size <= 0:
            raise DeduplicationError("signature_size must be positive")
        if self.max_bucket_size < 2:
            raise DeduplicationError("max_bucket_size must be at least 2")
        if self.max_candidate_pairs <= 0:
            raise DeduplicationError("max_candidate_pairs must be positive")


@dataclass(frozen=True, slots=True)
class PromptFingerprint:
    """Stable exact and normalized hashes for one query."""

    query_id: str
    exact_sha256: str
    normalized_sha256: str


@dataclass(frozen=True, slots=True)
class DuplicateCluster:
    """A set of queries that must remain on one side of a split boundary."""

    cluster_id: str
    query_ids: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    """Complete deterministic output of prompt deduplication."""

    config: DeduplicationConfig
    fingerprints: tuple[PromptFingerprint, ...]
    clusters: tuple[DuplicateCluster, ...]
    near_duplicate_pairs: tuple[tuple[str, str], ...]
    skipped_near_duplicate_buckets: int

    def cluster_id_by_query(self) -> dict[str, str]:
        """Return the duplicate-cluster ID assigned to every query."""
        return {
            query_id: cluster.cluster_id
            for cluster in self.clusters
            for query_id in cluster.query_ids
        }


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parents = list(range(size))
        self._ranks = [0] * size

    def find(self, item: int) -> int:
        parent = self._parents[item]
        if parent != item:
            self._parents[item] = self.find(parent)
        return self._parents[item]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self._ranks[left_root] < self._ranks[right_root]:
            left_root, right_root = right_root, left_root
        self._parents[right_root] = left_root
        if self._ranks[left_root] == self._ranks[right_root]:
            self._ranks[left_root] += 1


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_prompt(prompt: str) -> str:
    """Apply the conservative, versioned normalization used for duplicate checks."""
    normalized = unicodedata.normalize("NFKC", prompt)
    return " ".join(normalized.casefold().split())


def fingerprint_prompt(*, query_id: str, prompt: str) -> PromptFingerprint:
    """Create exact and normalized SHA-256 fingerprints without storing prompt text."""
    return PromptFingerprint(
        query_id=query_id,
        exact_sha256=_sha256_text(prompt),
        normalized_sha256=_sha256_text(normalize_prompt(prompt)),
    )


def _validate_queries(queries: tuple[QueryForSplitting, ...]) -> None:
    if not queries:
        raise DeduplicationError("at least one query is required")
    seen_ids: set[str] = set()
    for index, query in enumerate(queries):
        if not query.query_id.strip():
            raise DeduplicationError(f"queries[{index}].query_id must not be empty")
        if query.query_id in seen_ids:
            raise DeduplicationError(f"duplicate query_id: {query.query_id}")
        seen_ids.add(query.query_id)
        if not query.prompt.strip():
            raise DeduplicationError(f"query {query.query_id} has an empty prompt")
        if not query.task.strip():
            raise DeduplicationError(f"query {query.query_id} has an empty task")
        if not query.source.strip():
            raise DeduplicationError(f"query {query.query_id} has an empty source")
        if query.observed_at is not None and query.observed_at.tzinfo is None:
            raise DeduplicationError(f"query {query.query_id} observed_at must include a timezone")


def _shingle_hashes(prompt: str, *, size: int) -> frozenset[int]:
    tokens = _TOKEN_PATTERN.findall(normalize_prompt(prompt))
    if len(tokens) < size:
        shingles = tokens or [""]
    else:
        shingles = [
            "\x1f".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)
        ]
    return frozenset(
        int.from_bytes(hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest())
        for shingle in shingles
    )


def _signature(prompt: str, *, config: DeduplicationConfig) -> tuple[int, ...]:
    hashes = _shingle_hashes(prompt, size=config.shingle_size)
    return tuple(sorted(hashes)[: config.signature_size])


def _near_duplicate_pairs(
    queries: tuple[QueryForSplitting, ...],
    *,
    config: DeduplicationConfig,
) -> tuple[tuple[tuple[int, int], ...], int]:
    buckets: dict[int, list[int]] = defaultdict(list)
    for index, query in enumerate(queries):
        for signature_value in _signature(query.prompt, config=config):
            buckets[signature_value].append(index)

    candidates: set[tuple[int, int]] = set()
    skipped_buckets = 0
    for members in buckets.values():
        unique_members = sorted(set(members))
        if len(unique_members) < 2:
            continue
        if len(unique_members) > config.max_bucket_size:
            skipped_buckets += 1
            continue
        candidates.update(itertools.combinations(unique_members, 2))
        if len(candidates) > config.max_candidate_pairs:
            raise DeduplicationError(
                "near-duplicate candidate limit exceeded; lower max_bucket_size or "
                "raise max_candidate_pairs explicitly"
            )

    required_intersection_cache: dict[int, frozenset[int]] = {}

    def shingles(index: int) -> frozenset[int]:
        existing = required_intersection_cache.get(index)
        if existing is None:
            existing = _shingle_hashes(queries[index].prompt, size=config.shingle_size)
            required_intersection_cache[index] = existing
        return existing

    matches: list[tuple[int, int]] = []
    for left, right in sorted(candidates):
        left_shingles = shingles(left)
        right_shingles = shingles(right)
        similarity = len(left_shingles & right_shingles) / len(left_shingles | right_shingles)
        if similarity >= config.near_duplicate_threshold:
            matches.append((left, right))
    return tuple(matches), skipped_buckets


def deduplicate_queries(
    queries: tuple[QueryForSplitting, ...],
    *,
    config: DeduplicationConfig | None = None,
) -> DeduplicationResult:
    """Cluster exact, normalized, identified-lineage, and likely near duplicates."""
    settings = config or DeduplicationConfig()
    settings.validate()
    _validate_queries(queries)

    fingerprints = tuple(
        fingerprint_prompt(query_id=query.query_id, prompt=query.prompt) for query in queries
    )
    union_find = _UnionFind(len(queries))
    reason_members: dict[str, set[int]] = defaultdict(set)

    def union_groups(groups: dict[object, list[int]], *, reason: str) -> None:
        for members in groups.values():
            if len(members) < 2:
                continue
            reason_members[reason].update(members)
            first = members[0]
            for member in members[1:]:
                union_find.union(first, member)

    exact_groups: dict[object, list[int]] = defaultdict(list)
    normalized_groups: dict[object, list[int]] = defaultdict(list)
    source_groups: dict[object, list[int]] = defaultdict(list)
    lineage_groups: dict[object, list[int]] = defaultdict(list)
    for index, (query, fingerprint) in enumerate(zip(queries, fingerprints, strict=True)):
        exact_groups[fingerprint.exact_sha256].append(index)
        normalized_groups[fingerprint.normalized_sha256].append(index)
        if query.source_query_id is not None:
            source_groups[(query.source, query.source_query_id)].append(index)
        if query.lineage_id is not None:
            lineage_groups[query.lineage_id].append(index)

    union_groups(exact_groups, reason="exact_prompt")
    union_groups(normalized_groups, reason="normalized_prompt")
    union_groups(source_groups, reason="source_identity")
    union_groups(lineage_groups, reason="augmentation_lineage")

    near_pairs, skipped_buckets = _near_duplicate_pairs(queries, config=settings)
    for left, right in near_pairs:
        union_find.union(left, right)
        reason_members["near_duplicate"].update((left, right))

    cluster_members: dict[int, list[int]] = defaultdict(list)
    for index in range(len(queries)):
        cluster_members[union_find.find(index)].append(index)

    clusters: list[DuplicateCluster] = []
    for members in cluster_members.values():
        query_ids = tuple(sorted(queries[index].query_id for index in members))
        cluster_digest = _sha256_text("\x1f".join(query_ids))
        member_set = set(members)
        reasons = tuple(
            sorted(
                reason
                for reason, related_members in reason_members.items()
                if len(member_set & related_members) >= 2
            )
        )
        clusters.append(
            DuplicateCluster(
                cluster_id=f"dup-{cluster_digest[:20]}",
                query_ids=query_ids,
                reasons=reasons,
            )
        )

    clusters.sort(key=lambda cluster: cluster.cluster_id)
    named_near_pairs = tuple(
        sorted(
            (
                min(queries[left].query_id, queries[right].query_id),
                max(queries[left].query_id, queries[right].query_id),
            )
            for left, right in near_pairs
        )
    )
    return DeduplicationResult(
        config=settings,
        fingerprints=tuple(sorted(fingerprints, key=lambda value: value.query_id)),
        clusters=tuple(clusters),
        near_duplicate_pairs=named_near_pairs,
        skipped_near_duplicate_buckets=skipped_buckets,
    )
