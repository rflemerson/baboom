"""Decide which projections a change can reach, and reprice only those.

A change first expires the rows it may have made wrong, at once, so the
catalog never serves them while the refresh waits; then it schedules a refresh
of every offer it reached, old and new, after the transaction commits. Calls
in one transaction schedule one task each: the refresh is idempotent, and a
rolled-back savepoint takes its tasks with it.

Expiring takes the offers' row locks, as a refresh does and until the same
transaction ends. A refresh that read facts before the change then publishes
before the expiry runs, which expires its rows; one that starts after waits for
the change to commit and reads it. Neither can leave an old price valid.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import Category
from offers.models import Offer
from promotions.models import PromotionRevision, PromotionScope, PurchaseRoute

from .models import OfferScenarioProjection
from .tasks import refresh_projections

# Scope kinds that name offers through a plain relation. The others
# (store categories, channels, merchants) reach every offer.
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
    """Expire what a change may have made wrong; refresh what it reached."""

    def offers(self, offer_ids: list[int] | None, *, expire: bool = False) -> None:
        """Refresh these offers, or every linked one with None, after commit."""
        if expire:
            self._lock(offer_ids)
            rows = OfferScenarioProjection.objects.all()
            if offer_ids is not None:
                rows = rows.filter(offer_id__in=offer_ids)
            rows.update(expires_at=timezone.now())
        ids = None if offer_ids is None else sorted(set(offer_ids))
        if ids == []:
            return
        transaction.on_commit(lambda: refresh_projections.delay(offer_ids=ids))

    def store(self, store_slug: str) -> None:
        """Refresh a store's linked offers after a crawl changed them."""
        self.offers(
            list(
                Offer.objects.filter(
                    store_slug=store_slug,
                    product_store__isnull=False,
                ).values_list("pk", flat=True),
            )
            if store_slug
            else None,
        )

    def promotion(self, revision_id: int) -> None:
        """Expire rows any revision of this promotion priced; refresh its reach.

        Every revision counts: a suspended or replaced one may have priced
        offers the current one no longer reaches.
        """
        revisions = set(
            PromotionRevision.objects.filter(
                promotion__revisions=revision_id,
            ).values_list("pk", flat=True),
        )
        reached = self._reach(revisions)
        self._lock(reached)
        rows = OfferScenarioProjection.objects.exclude(explanation__applied=[])
        if reached is not None:
            rows = rows.filter(offer_id__in=reached)
        stale = [
            pk
            for pk, explanation in rows.values_list("pk", "explanation")
            if revisions & set((explanation or {}).get("applied") or ())
        ]
        OfferScenarioProjection.objects.filter(pk__in=stale).update(
            expires_at=timezone.now(),
        )
        self.offers(reached)

    def eligibility(self, offer_ids: list[int]) -> None:
        """Expire what these offers' promotions gave, then reprice them.

        For a change that may take a promotion away from an offer (another
        product, brand or category, a moved category): the rows that applied
        a revision stop serving at once; the others never relied on one.
        """
        self._lock(offer_ids)
        OfferScenarioProjection.objects.filter(offer_id__in=offer_ids).exclude(
            explanation__applied=[],
        ).update(expires_at=timezone.now())
        self.offers(offer_ids)

    def route(self, route: PurchaseRoute, before: PurchaseRoute | None) -> None:
        """Expire the offers a route served and serves: never serve its old link."""
        ids = set(self._route_offers(route))
        if before is not None:
            ids.update(self._route_offers(before))
        self.offers(sorted(ids), expire=True)

    def unlink(self, offer_id: int) -> None:
        """Drop an unlinked offer's projections; nothing ranks it any more."""
        OfferScenarioProjection.objects.filter(offer_id=offer_id).delete()

    @staticmethod
    def _lock(offer_ids: list[int] | None) -> None:
        """Lock the linked offers among these (all with None) in a refresh's order."""
        linked = Offer.objects.filter(product_store__isnull=False)
        if offer_ids is not None:
            linked = linked.filter(pk__in=offer_ids)
        with transaction.atomic():
            list(
                Offer.objects.select_for_update()
                .filter(pk__in=linked.values("pk"))
                .order_by("pk"),
            )

    @staticmethod
    def _reach(revisions: set[int]) -> list[int] | None:
        """Return the offers these revisions target, or None for every offer."""
        scopes = PromotionScope.objects.filter(
            revision__in=revisions,
            role=PromotionScope.Role.TARGET,
            mode=PromotionScope.Mode.INCLUDE,
        ).values_list("kind", "ref_id")
        reach = Q()
        for kind, ref_id in scopes:
            if kind == PromotionScope.Kind.CATEGORY:
                reach |= Q(product_store__product__category__in=_subtree(ref_id))
                continue
            lookup = _OFFER_LOOKUPS.get(kind)
            if lookup is None:
                return None
            reach |= Q(**{lookup: ref_id})
        if not reach:
            return None
        return list(Offer.objects.filter(reach).values_list("pk", flat=True).distinct())

    @staticmethod
    def _route_offers(route: PurchaseRoute) -> list[int]:
        if route.offer_id is not None:
            return [route.offer_id]
        return list(
            Offer.objects.filter(
                listing_variant__listing_id=route.listing_id,
            ).values_list("pk", flat=True),
        )


def _subtree(category_id: int | None) -> list[int]:
    """Return a category and its descendants."""
    node = Category.objects.filter(pk=category_id).first()
    if node is None:
        return []
    return [node.pk, *node.get_descendants().values_list("pk", flat=True)]
