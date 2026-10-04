"""Recompute projections after the facts or rules they depend on change."""

from __future__ import annotations

from django.db import transaction
from django.dispatch import receiver

from offers.signals import offers_observed
from promotions.signals import revision_changed

from .tasks import refresh_projections


@receiver(offers_observed, dispatch_uid="pricing-offers")
def on_offers_observed(
    sender: object, *, store_slug: str = "", **kwargs: object
) -> None:
    """Reprice a store after a crawl changed its offers, once it commits."""
    _ = sender, kwargs
    transaction.on_commit(lambda: refresh_projections.delay(store_slug or None))


@receiver(revision_changed, dispatch_uid="pricing-revisions")
def on_revision_changed(sender: object, **kwargs: object) -> None:
    """Reprice every linked offer after a promotion changed, once it commits."""
    _ = sender, kwargs
    transaction.on_commit(lambda: refresh_projections.delay(None))
