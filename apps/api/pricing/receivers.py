"""Recompute projections after the facts or rules they depend on change.

Every dependency has a receiver: offers read by a crawl, promotion
revisions, purchase routes and their programmes, shipping and tax quotes,
public policies, catalog links, and the brand or category promotions scope
by. A change reprices only the offers it can reach, after commit. Where a
stale row would show a wrong link or price, it expires at once so the
catalog never serves it while the refresh runs.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import Product, ProductStore
from offers.models import Offer
from offers.signals import offers_observed
from promotions.models import PurchaseRoute
from promotions.signals import revision_changed

from .models import (
    OfferScenarioProjection,
    PricingPolicyRevision,
    ShippingQuote,
    TaxFeeQuote,
)
from .tasks import refresh_projections


def _reprice(offer_ids: list[int] | None, *, expire: bool = False) -> None:
    """Refresh these offers (every linked one with None) after commit."""
    if expire:
        rows = OfferScenarioProjection.objects.all()
        if offer_ids is not None:
            rows = rows.filter(offer_id__in=offer_ids)
        rows.update(expires_at=timezone.now())
    ids = None if offer_ids is None else sorted(set(offer_ids))
    transaction.on_commit(lambda: refresh_projections.delay(offer_ids=ids))


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
    _reprice(None)


def _route_offers(route: PurchaseRoute) -> list[int]:
    """Return the offers a route serves: its own, or its listing's."""
    if route.offer_id is not None:
        return [route.offer_id]
    return list(
        Offer.objects.filter(listing_variant__listing_id=route.listing_id).values_list(
            "pk",
            flat=True,
        ),
    )


@receiver(post_save, sender=PurchaseRoute, dispatch_uid="pricing-route-save")
@receiver(post_delete, sender=PurchaseRoute, dispatch_uid="pricing-route-delete")
def on_route_changed(
    sender: object, *, instance: PurchaseRoute, **kwargs: object
) -> None:
    """Expire a changed route's projections: never serve its old link."""
    _ = sender, kwargs
    _reprice(_route_offers(instance), expire=True)


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
    """Tracking compatibility changed: the rewards a route keeps may change."""
    _ = sender, kwargs
    if action in {"post_add", "post_remove", "post_clear"} and isinstance(
        instance,
        PurchaseRoute,
    ):
        _reprice(_route_offers(instance), expire=True)


@receiver(post_save, sender=ShippingQuote, dispatch_uid="pricing-shipping")
def on_shipping_quoted(
    sender: object, *, instance: ShippingQuote, **kwargs: object
) -> None:
    """Reprice a seller's offers when their shipping changes."""
    _ = sender, kwargs
    _reprice(
        list(
            Offer.objects.filter(
                seller_account_id=instance.seller_account_id
            ).values_list(
                "pk",
                flat=True,
            ),
        ),
    )


@receiver(post_save, sender=TaxFeeQuote, dispatch_uid="pricing-fees")
def on_fee_quoted(sender: object, **kwargs: object) -> None:
    """Reprice all offers on a tax or fee change; groups do not map to offers."""
    _ = sender, kwargs
    _reprice(None)


@receiver(post_save, sender=PricingPolicyRevision, dispatch_uid="pricing-policy")
def on_policy_saved(
    sender: object, *, instance: PricingPolicyRevision, **kwargs: object
) -> None:
    """Project a newly published policy."""
    _ = sender, kwargs
    if instance.published_at is not None:
        _reprice(None)


@receiver(post_save, sender=ProductStore, dispatch_uid="pricing-link")
def on_link_saved(sender: object, *, instance: ProductStore, **kwargs: object) -> None:
    """Reprice a newly linked offer; product scopes now reach it."""
    _ = sender, kwargs
    if instance.offer_id is not None:
        _reprice([instance.offer_id])


@receiver(post_save, sender=Product, dispatch_uid="pricing-product")
def on_product_saved(sender: object, *, instance: Product, **kwargs: object) -> None:
    """Brand or category scopes may now reach, or no longer reach, its offers."""
    _ = sender, kwargs
    _reprice(
        list(
            Offer.objects.filter(
                Q(product_store__product=instance),
            ).values_list("pk", flat=True),
        ),
    )
