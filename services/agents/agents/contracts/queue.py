"""Queue-facing contracts for launching Dagster runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueueWorkItem:
    """Normalized queue item required to launch one Dagster run."""

    item_id: int
    url: str
    store_name: str
    store_slug: str
