"""Background recomputation of the projections the catalog ranks by."""

from __future__ import annotations

from celery import shared_task
from django.db import transaction

from .models import ProjectionRefreshRequest
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


@shared_task
def drain_projection_requests() -> int:
    """Reprice the offers changes queued, merged into one refresh.

    Requests are taken under ``skip_locked``, so two workers never take the
    same one. They are deleted before the refresh: one that fails loses them,
    and the hourly refresh reprices those offers instead.
    """
    with transaction.atomic():
        taken = list(
            ProjectionRefreshRequest.objects.select_for_update(skip_locked=True)
            .order_by("pk")
            .values_list("pk", "offer_ids")
        )
        if not taken:
            return 0
        ProjectionRefreshRequest.objects.filter(
            pk__in=[pk for pk, _ids in taken]
        ).delete()
    offer_ids = (
        None
        if any(ids is None for _pk, ids in taken)
        else sorted({pk for _request, ids in taken for pk in ids})
    )
    service = ProjectionService()
    return service.refresh(service.linked_offers(None, offer_ids))
