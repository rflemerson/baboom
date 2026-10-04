"""Load facts and rules from the database, run the engine, persist quotes.

This is the only place the pure engine meets the ORM. It reads in batches,
turns rows into the engine's frozen inputs and, when asked, keeps a quote
with the snapshot that reproduces the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import OuterRef, Q, Subquery

from commerce.models import Market
from core.models import Category, ProductStore
from offers.models import Offer, OfferPriceObservation, StockStatus
from promotions.models import PromotionRevision, PurchaseRoute

from .domain.conditions import (
    Amounts,
)
from .domain.scopes import reaching
from .domain.types import (
    CompatibilityFact,
    EffectRule,
    OfferFact,
    PriceFact,
    RevisionRule,
    RewardTermsFact,
    RouteFact,
    ScopeRule,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import timedelta

    from .models import PricingPolicyRevision

LEGACY_PRICE_ID = 0
EMPTY_AMOUNTS = Amounts(
    before_discounts=Decimal(0),
    after_item_discounts=Decimal(0),
    after_order_discounts=Decimal(0),
    shipping=None,
    quantity=0,
)


@dataclass(frozen=True)
class Facts:
    """Offers, prices, revisions and purchase routes loaded for a set of offers."""

    offers: dict[int, OfferFact]
    prices: tuple[PriceFact, ...]
    revisions: tuple[RevisionRule, ...]
    routes: tuple[RouteFact, ...] = ()


class FactLoader:
    """Turn rows into the engine's inputs, in a fixed number of queries."""

    def load(
        self,
        offer_ids: Iterable[int],
        policy: PricingPolicyRevision,
    ) -> Facts:
        """Load everything the engine reads about these offers."""
        ids = sorted(set(offer_ids))
        offers = self.offers(ids)
        return Facts(
            offers=offers,
            prices=self.prices(ids, policy.freshness),
            revisions=reaching(self.revisions(), offers.values()),
            routes=self.routes(ids),
        )

    @staticmethod
    def routes(ids: list[int]) -> tuple[RouteFact, ...]:
        """Return the curated purchase routes of these offers, or of their listings."""
        listing_of = dict(
            Offer.objects.filter(pk__in=ids).values_list(
                "pk",
                "listing_variant__listing_id",
            ),
        )
        rows = PurchaseRoute.objects.filter(
            Q(offer_id__in=ids) | Q(listing_id__in=set(listing_of.values()) - {None}),
        ).prefetch_related("compatible_programs")
        facts: list[RouteFact] = []
        for route in rows:
            targets = (
                [route.offer_id]
                if route.offer_id is not None
                else [
                    pk
                    for pk, listing in listing_of.items()
                    if listing == route.listing_id
                ]
            )
            facts.extend(
                RouteFact(
                    id=route.pk,
                    offer_id=offer_id,
                    kind=route.kind,
                    url=route.url,
                    program_id=route.program_id,
                    instructions=route.instructions,
                    fixes_variant=route.fixes_variant,
                    fixes_seller=route.fixes_seller,
                    compatible_programs=frozenset(
                        program.pk for program in route.compatible_programs.all()
                    ),
                )
                for offer_id in targets
            )
        return tuple(facts)

    @staticmethod
    def offers(ids: list[int]) -> dict[int, OfferFact]:
        """Return each offer with its market, seller and catalog product."""
        rows = Offer.objects.filter(pk__in=ids).select_related(
            "listing_variant__listing__market",
            "seller_account",
        )
        namespaces = {
            market.namespace: market
            for market in Market.objects.filter(
                namespace__in={offer.store_slug for offer in rows},
            )
        }
        links = {
            link.offer_id: link.product
            for link in ProductStore.objects.filter(offer_id__in=ids).select_related(
                "product__category",
            )
        }
        lineage = FactLoader._category_lineage(
            {link.category for link in links.values() if link.category is not None},
        )
        facts: dict[int, OfferFact] = {}
        for offer in rows:
            variant = offer.listing_variant
            market = (
                variant.listing.market if variant else namespaces.get(offer.store_slug)
            )
            if market is None:
                continue
            product = links.get(offer.pk)
            categories = (
                lineage.get(product.category_id, frozenset())
                if product is not None
                else frozenset()
            )
            facts[offer.pk] = OfferFact(
                id=offer.pk,
                market_id=market.pk,
                channel_id=market.channel_id,
                seller_id=offer.seller_account_id,
                listing_id=variant.listing_id if variant else None,
                listing_variant_id=variant.pk if variant else None,
                product_id=product.pk if product else None,
                brand_id=product.brand_id if product else None,
                category_ids=categories,
                external_categories=frozenset({offer.category} - {""}),
                purchasable=(
                    offer.delisted_at is None
                    and offer.current_stock_status in StockStatus.purchasable()
                ),
                seller_is_owner=bool(
                    offer.seller_account and offer.seller_account.is_channel_owner,
                ),
            )
        return facts

    @staticmethod
    def prices(ids: list[int], window: timedelta) -> tuple[PriceFact, ...]:
        """Return the standing observation of each condition of each offer.

        The newest row of a condition decides: if it was withdrawn, the
        condition is gone, whatever older rows say. An offer with no
        observation at all is priced by its legacy current price, marked
        ``legacy_unknown``; an offer with any observation never falls back.
        """
        latest = OfferPriceObservation.objects.filter(
            offer_id=OuterRef("offer_id"),
            condition_key=OuterRef("condition_key"),
        ).order_by("-observed_at", "-pk")
        rows = (
            OfferPriceObservation.objects.filter(
                offer_id__in=ids,
                pk=Subquery(latest.values("pk")[:1]),
            )
            .select_related("payment_method")
            .order_by("offer_id", "condition_key", "-observed_at", "-pk")
        )
        newest: dict[tuple[int, str], OfferPriceObservation] = {}
        for row in rows:
            newest.setdefault((row.offer_id, row.condition_key), row)
        observed = {offer_id for offer_id, _key in newest}
        # Migrated history says nothing a typed read did not say better: once
        # an offer has typed observations, its legacy rows stop competing.
        typed_offers = {
            row.offer_id
            for row in newest.values()
            if row.semantics != OfferPriceObservation.Semantics.LEGACY_UNKNOWN
        }
        latest = {
            key: row
            for key, row in newest.items()
            if row.withdrawn_at is None
            and (
                row.offer_id not in typed_offers
                or row.semantics != OfferPriceObservation.Semantics.LEGACY_UNKNOWN
            )
        }
        facts = [
            PriceFact(
                id=row.pk,
                offer_id=row.offer_id,
                role=row.role,
                amount=row.amount,
                currency=row.currency_id,
                payment_scope=row.payment_scope,
                payment_method=row.payment_method.code if row.payment_method else "",
                installment_count=row.installment_count,
                installment_amount=row.installment_amount,
                interest=row.interest,
                composition=row.composition,
                included_adjustments=tuple(
                    str(item.get("kind"))
                    for item in row.included_adjustments or []
                    if isinstance(item, dict)
                ),
                semantics=row.semantics,
                evidence_level=row.evidence_level,
                source_field=row.source_field,
                observed_at=row.observed_at,
                fresh_until=row.confirmed_at + window,
                quantity_min=row.quantity_min,
                quantity_max=row.quantity_max,
                amount_basis=row.amount_basis,
                capture_stage=row.capture_stage,
                context=FactLoader._context_pairs(row.context),
            )
            for row in latest.values()
        ]
        legacy = Offer.objects.filter(pk__in=set(ids) - observed).exclude(
            current_price__isnull=True,
        )
        markets = {
            market.namespace: market.currency_id
            for market in Market.objects.filter(
                namespace__in={offer.store_slug for offer in legacy},
            )
        }
        facts.extend(
            PriceFact(
                id=LEGACY_PRICE_ID,
                offer_id=offer.pk,
                role="payable",
                amount=offer.current_price,
                currency=markets.get(offer.store_slug, "BRL"),
                semantics="legacy_unknown",
                source_field="Offer.current_price",
                fresh_until=(offer.last_seen_at or offer.updated_at) + window,
            )
            for offer in legacy
        )
        return tuple(facts)

    @staticmethod
    def revisions() -> tuple[RevisionRule, ...]:
        """Return the revision in force of every promotion, as engine rules."""
        published = (
            PromotionRevision.objects.filter(
                status__in=(
                    PromotionRevision.Status.EXECUTABLE,
                    PromotionRevision.Status.INFORMATIVE,
                    PromotionRevision.Status.SUSPENDED,
                    PromotionRevision.Status.ARCHIVED,
                ),
            )
            .order_by("promotion_id", "-number")
            .prefetch_related(
                "effects__reward_terms",
                "scopes",
                "codes",
                "compatibility",
            )
        )
        newest: dict[int, PromotionRevision] = {}
        for revision in published:
            newest.setdefault(revision.promotion_id, revision)
        return tuple(FactLoader._rule(revision) for revision in newest.values())

    @staticmethod
    def _category_lineage(categories: set[Category]) -> dict[int, frozenset[int]]:
        """Return each category with its ancestors, in one query for all of them.

        A materialized path names every ancestor by prefix, so the ancestors of
        every category of a batch come from a single lookup by path.
        """
        if not categories:
            return {}
        step = Category.steplen
        prefixes = {
            category.path[:end]
            for category in categories
            for end in range(step, len(category.path), step)
        }
        by_path = dict(
            Category.objects.filter(path__in=prefixes).values_list("path", "pk"),
        )
        return {
            category.pk: frozenset(
                [
                    category.pk,
                    *(
                        by_path[category.path[:end]]
                        for end in range(step, len(category.path), step)
                        if category.path[:end] in by_path
                    ),
                ],
            )
            for category in categories
        }

    @staticmethod
    def _context_pairs(context: object) -> tuple[tuple[str, str], ...]:
        """Flatten an observation's context into sorted, hashable pairs."""
        if not isinstance(context, dict):
            return ()
        return tuple(sorted((str(key), str(value)) for key, value in context.items()))

    @staticmethod
    def _rule(revision: PromotionRevision) -> RevisionRule:
        """Translate a revision and everything it owns into an engine rule."""
        effects = []
        for effect in revision.effects.all():
            terms = getattr(effect, "reward_terms", None)
            effects.append(
                EffectRule(
                    position=effect.position,
                    kind=effect.kind,
                    stage=effect.stage,
                    basis=effect.basis,
                    target=effect.target,
                    allocation=effect.allocation,
                    params=dict(effect.parameters or {}),
                    cap=effect.cap,
                    max_applications=effect.max_applications,
                    consumes_units=effect.consumes_units,
                    reward=(
                        RewardTermsFact(
                            credited_as=terms.credited_as,
                            rate=terms.rate,
                            cap=terms.cap,
                            cap_period=terms.cap_period,
                            minimum=terms.minimum,
                            includes_shipping=terms.includes_shipping,
                            eligible_basis=terms.eligible_basis,
                            program_id=terms.program_id,
                            credit_delay_days=terms.credit_delay_days,
                            tracking_required=terms.tracking_required,
                        )
                        if terms is not None
                        else None
                    ),
                ),
            )
        return RevisionRule(
            id=revision.pk,
            promotion_id=revision.promotion_id,
            number=revision.number,
            status=revision.status,
            currency=revision.currency_id,
            timezone=revision.timezone,
            conditions=dict(revision.conditions or {}),
            effects=tuple(effects),
            scopes=tuple(
                ScopeRule(
                    role=scope.role,
                    mode=scope.mode,
                    kind=scope.kind,
                    ref_id=scope.ref_id,
                    external_ref=scope.external_ref,
                    combine=scope.combine,
                )
                for scope in revision.scopes.all()
            ),
            codes=tuple((code.kind, code.code) for code in revision.codes.all()),
            compatibility=tuple(
                CompatibilityFact(
                    other_kind=rule.other_kind,
                    other_ref=rule.other_ref,
                    verdict=rule.verdict,
                    chooser=rule.chooser,
                )
                for rule in revision.compatibility.all()
            ),
            ordering=tuple(
                (int(edge["before"]), int(edge["after"]))
                for edge in revision.ordering or []
                if isinstance(edge, dict)
            ),
            starts_at=revision.starts_at,
            ends_at=revision.ends_at,
            content_hash=revision.content_hash,
        )
