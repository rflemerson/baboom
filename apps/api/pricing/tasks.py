"""Background recomputation of the projections the catalog ranks by."""

from __future__ import annotations

from celery import shared_task

from .projections import ProjectionService


@shared_task
def refresh_projections(
    store_slug: str | None = None,
    offer_ids: list[int] | None = None,
) -> int:
    """Recompute projections of some offers, one store's, or every linked one.

    Idempotent: a refresh replaces rows, so running it twice changes nothing.
    The hourly schedule also drops amounts whose promotions or prices expired.
    """
    service = ProjectionService()
    return service.refresh(service.linked_offers(store_slug, offer_ids))
