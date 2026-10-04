"""Reprice projections after a change made outside pricing.

Crawls and promotion publication announce themselves with their own
signals, so neither app imports pricing. Catalog links, products, categories
and routes are edited in the admin, so their model signals are the only
hook; a ``pre_save`` keeps the state being replaced, because the offers it
reached need repricing too. Pricing's own writes call ``Repricing``.
"""

from __future__ import annotations

from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from core.events import category_moved
from core.models import Category, Product, ProductStore
from offers.models import Offer
from offers.signals import offers_observed
from promotions.models import PurchaseRoute
from promotions.signals import revision_changed

from .invalidation import Repricing

M2M_CHANGES = frozenset({"post_add", "post_remove", "post_clear"})


@receiver(offers_observed, dispatch_uid="pricing-offers")
def on_offers_observed(
    sender: object, *, store_slug: str = "", **kwargs: object
) -> None:
    """Reprice a store after a crawl changed its offers."""
    _ = sender, kwargs
    Repricing().store(store_slug)


@receiver(revision_changed, dispatch_uid="pricing-revisions")
def on_revision_changed(sender: object, *, revision_id: int, **kwargs: object) -> None:
    """Expire prices a promotion gave, then reprice the offers it reaches."""
    _ = sender, kwargs
    Repricing().promotion(revision_id)


@receiver(pre_save, sender=PurchaseRoute, dispatch_uid="pricing-route-before")
@receiver(pre_save, sender=ProductStore, dispatch_uid="pricing-link-before")
@receiver(pre_save, sender=Product, dispatch_uid="pricing-product-before")
def keep_previous(sender: type, *, instance: object, **kwargs: object) -> None:
    """Remember the stored row a save replaces."""
    _ = kwargs
    pk = getattr(instance, "pk", None)
    instance.__dict__["_pricing_before"] = (
        sender.objects.filter(pk=pk).first() if pk is not None else None
    )


def _before(instance: object) -> object | None:
    return instance.__dict__.pop("_pricing_before", None)


@receiver(post_save, sender=PurchaseRoute, dispatch_uid="pricing-route-save")
@receiver(post_delete, sender=PurchaseRoute, dispatch_uid="pricing-route-delete")
def on_route_changed(
    sender: object, *, instance: PurchaseRoute, **kwargs: object
) -> None:
    """Expire the offers a route served and serves."""
    _ = sender, kwargs
    before = _before(instance)
    Repricing().route(instance, before if isinstance(before, PurchaseRoute) else None)


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
    reverse: bool,
    pk_set: set[int] | None,
    **kwargs: object,
) -> None:
    """Expire routes whose tracked programmes changed, from either side.

    Seen from a programme, a clear removes its routes before ``post_clear``
    can find them: they are kept at ``pre_clear``, and likewise at
    ``pre_remove`` when no keys are given.
    """
    _ = sender, kwargs
    if reverse and pk_set is None and action in {"pre_clear", "pre_remove"}:
        instance.__dict__["_pricing_routes"] = list(
            PurchaseRoute.objects.filter(compatible_programs=instance),
        )
        return
    if action not in M2M_CHANGES:
        return
    if not reverse and isinstance(instance, PurchaseRoute):
        Repricing().route(instance, None)
        return
    kept = instance.__dict__.pop("_pricing_routes", None)
    routes = (
        kept if kept is not None else PurchaseRoute.objects.filter(pk__in=pk_set or ())
    )
    for route in routes:
        Repricing().route(route, None)


@receiver(post_save, sender=ProductStore, dispatch_uid="pricing-link")
def on_link_saved(sender: object, *, instance: ProductStore, **kwargs: object) -> None:
    """Reprice a linked offer; drop an offer the link no longer names.

    An offer that keeps its link but changes product may leave the scope of
    a promotion: what it applied expires at once.
    """
    _ = sender, kwargs
    before = _before(instance)
    if isinstance(before, ProductStore) and before.offer_id not in (
        None,
        instance.offer_id,
    ):
        Repricing().unlink(before.offer_id)
    if instance.offer_id is None:
        return
    if (
        isinstance(before, ProductStore)
        and before.offer_id == instance.offer_id
        and before.product_id != instance.product_id
    ):
        Repricing().eligibility([instance.offer_id])
        return
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
    """Reprice a product's offers; brand or category scopes may now differ.

    A changed brand or category can take a promotion away: what the offers
    applied expires at once.
    """
    _ = sender, kwargs
    before = _before(instance)
    offers = list(
        Offer.objects.filter(product_store__product=instance).values_list(
            "pk",
            flat=True,
        ),
    )
    if isinstance(before, Product) and (
        before.brand_id != instance.brand_id
        or before.category_id != instance.category_id
    ):
        Repricing().eligibility(offers)
        return
    Repricing().offers(offers)


@receiver(post_save, sender=Category, dispatch_uid="pricing-category")
def on_category_saved(sender: object, *, instance: Category, **kwargs: object) -> None:
    """Reprice offers below a moved or edited category; scopes walk the tree."""
    _ = sender, kwargs
    tree = [instance.pk, *instance.get_descendants().values_list("pk", flat=True)]
    Repricing().offers(
        list(
            Offer.objects.filter(
                product_store__product__category__in=tree,
            ).values_list("pk", flat=True),
        ),
    )


@receiver(category_moved, dispatch_uid="pricing-category-moved")
def on_category_moved(sender: object, *, category_id: int, **kwargs: object) -> None:
    """Expire what offers below a moved category priced by their old ancestors."""
    _ = sender, kwargs
    category = Category.objects.filter(pk=category_id).first()
    if category is None:
        return
    tree = [category.pk, *category.get_descendants().values_list("pk", flat=True)]
    Repricing().eligibility(
        list(
            Offer.objects.filter(
                product_store__product__category__in=tree,
            ).values_list("pk", flat=True),
        ),
    )
