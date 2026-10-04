"""Decide which projections a change can reach, and reprice only those."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from offers.models import Offer
from promotions.models import PromotionScope, PurchaseRoute

from .models import OfferScenarioProjection
from .tasks import refresh_projections

# Scope kinds that name offers through a plain relation. The others
# (category trees, store categories, channels, merchants) reprice everything.
_OFFER_LOOKUPS = {
    PromotionScope.Kind.OFFER: "pk",
    PromotionScope.Kind.LISTING_VARIANT: "listing_variant_id",
    PromotionScope.Kind.LISTING: "listing_variant__listing_id",
    PromotionScope.Kind.SELLER_ACCOUNT: "seller_account_id",
    PromotionScope.Kind.MARKET: "seller_account__market_id",
    PromotionScope.Kind.PRODUCT: "product_store__product_id",
    PromotionScope.Kind.BRAND: "product_store__product__brand_id",
}


class Repricing:
    """Schedule refreshes after commit; expire rows that must not be served."""

    def offers(self, offer_ids: list[int] | None, *, expire: bool = False) -> None:
        """Refresh these offers, or every linked one with None."""
        if expire:
            rows = OfferScenarioProjection.objects.all()
            if offer_ids is not None:
                rows = rows.filter(offer_id__in=offer_ids)
            rows.update(expires_at=timezone.now())
        ids = None if offer_ids is None else sorted(set(offer_ids))
        transaction.on_commit(lambda: refresh_projections.delay(offer_ids=ids))

    def store(self, store_slug: str) -> None:
        """Refresh a store after a crawl changed its offers."""
        transaction.on_commit(lambda: refresh_projections.delay(store_slug or None))

    def promotion(self, revision_id: int) -> None:
        """Refresh the offers any revision of this promotion targets.

        Every revision counts: a new one may drop offers the previous reached.
        """
        scopes = PromotionScope.objects.filter(
            revision__promotion__revisions=revision_id,
            role=PromotionScope.Role.TARGET,
            mode=PromotionScope.Mode.INCLUDE,
        ).values_list("kind", "ref_id")
        reach = Q()
        for kind, ref_id in scopes:
            lookup = _OFFER_LOOKUPS.get(kind)
            if lookup is None:
                self.offers(None)
                return
            reach |= Q(**{lookup: ref_id})
        if not reach:
            self.offers(None)
            return
        self.offers(
            list(Offer.objects.filter(reach).values_list("pk", flat=True).distinct()),
        )

    def route(self, route: PurchaseRoute) -> None:
        """Expire and refresh the offers a route serves: never serve its old link."""
        if route.offer_id is not None:
            ids = [route.offer_id]
        else:
            ids = list(
                Offer.objects.filter(
                    listing_variant__listing_id=route.listing_id,
                ).values_list("pk", flat=True),
            )
        self.offers(ids, expire=True)

    def unlink(self, offer_id: int) -> None:
        """Drop an unlinked offer's projections; nothing ranks it any more."""
        OfferScenarioProjection.objects.filter(offer_id=offer_id).delete()
