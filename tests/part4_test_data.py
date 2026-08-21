"""Synthetic, timestamped Part 4 records shared by leakage tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lfm_model_router.data.deduplication import QueryForSplitting
from lfm_model_router.data.splits import ModelForSplitting


def make_queries() -> tuple[QueryForSplitting, ...]:
    """Return enough tasks and dates to exercise every required split."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    prompts = {
        0: "Exactly duplicated prompt",
        1: "Exactly duplicated prompt",
        2: "  NORMALIZED\n prompt  text ",
        3: "normalized prompt text",
        4: " ".join(f"nearword{index}" for index in range(24)),
        5: " ".join([*(f"nearword{index}" for index in range(24)), "please"]),
        6: "Source identity variant alpha",
        7: "Source identity variant beta",
        8: "Synthetic augmentation parent form",
        9: "Synthetic augmentation child form",
    }
    queries: list[QueryForSplitting] = []
    for index in range(30):
        prompt = prompts.get(
            index,
            " ".join(f"unique{index}token{token}" for token in range(8)),
        )
        queries.append(
            QueryForSplitting(
                query_id=f"q-{index:02d}",
                prompt=prompt,
                task=f"task-{index // 3:02d}",
                source="synthetic-benchmark",
                source_query_id="source-pair" if index in (6, 7) else f"source-{index}",
                lineage_id="lineage-pair" if index in (8, 9) else None,
                observed_at=start + timedelta(days=index),
            )
        )
    queries.extend(
        (
            QueryForSplitting(
                query_id="probe-00",
                prompt="Behavioral anchor prompt",
                task="probe-task",
                source="synthetic-probes",
                source_query_id="probe-source",
                observed_at=start + timedelta(days=40),
                is_probe=True,
            ),
            QueryForSplitting(
                query_id="probe-copy",
                prompt="  behavioral ANCHOR prompt ",
                task="probe-task",
                source="synthetic-probes",
                source_query_id="probe-copy-source",
                observed_at=start + timedelta(days=41),
            ),
        )
    )
    return tuple(queries)


def make_models() -> tuple[ModelForSplitting, ...]:
    """Return models with aliases, six families, and distinct release dates."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return tuple(
        ModelForSplitting(
            model_id=f"model-{index:02d}",
            provider=f"provider-{index % 2}",
            family=f"family-{index // 2:02d}",
            version=f"v{index + 1}",
            aliases=(f"MODEL ALIAS {index:02d}", f"api/model-{index:02d}"),
            available_at=start + timedelta(days=30 * index),
        )
        for index in range(12)
    )
