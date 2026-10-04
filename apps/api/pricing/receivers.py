"""Reprice projections after a change made outside pricing.

Crawls and promotion publication announce themselves with their own
signals, so neither app imports pricing. Catalog links, products and routes
are edited in the admin, so their model signals are the only hook. Pricing's
own writes (policies) call ``Repricing`` directly.
"""

from __future__ import annotations

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from core.models import Product, ProductStore
from offers.models import Offer
from offers.signals import offers_observed
from promotions.models import PurchaseRoute
from promotions.signals import revision_changed

from .invalidation import Repricing


@receiver(offers_observed, dispatch_uid="pricing-offers")
def on_offers_observed(
    sender: object, *, store_slug: str = "", **kwargs: object
) -> None:
    """Reprice a store after a crawl changed its offers."""
    _ = sender, kwargs
    Repricing().store(store_slug)


@receiver(revision_changed, dispatch_uid="pricing-revisions")
def on_revision_changed(sender: object, *, revision_id: int, **kwargs: object) -> None:
    """Reprice the offers a promotion targets."""
    _ = sender, kwargs
    Repricing().promotion(revision_id)


@receiver(post_save, sender=PurchaseRoute, dispatch_uid="pricing-route-save")
@receiver(post_delete, sender=PurchaseRoute, dispatch_uid="pricing-route-delete")
def on_route_changed(
    sender: object, *, instance: PurchaseRoute, **kwargs: object
) -> None:
    """Expire a changed route's projections."""
    _ = sender, kwargs
    Repricing().route(instance)


@receiver(
    m2m_changed,
    sender=PurchaseRoute.compatible_programs.through,
    dispatch_uid="pricing-route-programs",
)
def on_route_programs_changed(
    sender: object,
    *,
    instance: object,
    action: str,
    **kwargs: object,
) -> None:
    """Expire a route whose tracked programmes changed."""
    _ = sender, kwargs
    if action in {"post_add", "post_remove", "post_clear"} and isinstance(
        instance,
        PurchaseRoute,
    ):
        Repricing().route(instance)


@receiver(post_save, sender=ProductStore, dispatch_uid="pricing-link")
def on_link_saved(sender: object, *, instance: ProductStore, **kwargs: object) -> None:
    """Reprice a newly linked offer; product scopes now reach it."""
    _ = sender, kwargs
    if instance.offer_id is not None:
        Repricing().offers([instance.offer_id])


@receiver(post_delete, sender=ProductStore, dispatch_uid="pricing-unlink")
def on_link_deleted(
    sender: object, *, instance: ProductStore, **kwargs: object
) -> None:
    """Drop an unlinked offer's projections; deleting a product cascades here."""
    _ = sender, kwargs
    if instance.offer_id is not None:
        Repricing().unlink(instance.offer_id)


@receiver(post_save, sender=Product, dispatch_uid="pricing-product")
def on_product_saved(sender: object, *, instance: Product, **kwargs: object) -> None:
    """Reprice a product's offers; brand or category scopes may now differ."""
    _ = sender, kwargs
    Repricing().offers(
        list(
            Offer.objects.filter(product_store__product=instance).values_list(
                "pk",
                flat=True,
            ),
        ),
    )
