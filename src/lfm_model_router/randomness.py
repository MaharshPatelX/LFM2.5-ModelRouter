"""Deterministic random-state helpers."""

from __future__ import annotations

import random


def seed_python(seed: int) -> None:
    """Seed Python's process-wide pseudorandom generator."""
    if seed < 0:
        raise ValueError("seed must be non-negative")
    random.seed(seed)
