"""Background recomputation of the projections the catalog ranks by."""

from __future__ import annotations

from celery import shared_task

from offers.models import Offer

from .projections import ProjectionService, linked_offer_ids


@shared_task
def refresh_projections(store_slug: str | None = None) -> int:
    """Recompute projections of one store's linked offers, or of all of them.

    Idempotent: a refresh replaces rows, so running it twice changes nothing.
    The hourly schedule also drops amounts whose promotions or prices expired.
    """
    ids = linked_offer_ids()
    if store_slug:
        ids = list(
            Offer.objects.filter(pk__in=ids, store_slug=store_slug).values_list(
                "pk",
                flat=True,
            ),
        )
    return ProjectionService().refresh(ids)
