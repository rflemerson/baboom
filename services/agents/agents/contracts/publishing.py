"""Contracts used by the publishing stage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublishOriginContext:
    """Normalized source context used while publishing analyzed items."""

    item_id: int
    page_id: int | None
    page_url: str
    store_slug: str
    item: dict


@dataclass(frozen=True, slots=True)
class PublishItemResult:
    """Result of publishing one analyzed item plus bookkeeping metadata."""

    result: dict
    variant_created: bool
