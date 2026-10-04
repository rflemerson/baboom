"""Load facts and rules from the database, run the engine, persist quotes.

This is the only place the pure engine meets the ORM. It reads in batches,
turns rows into the engine's frozen inputs and, when asked, keeps a quote
with the snapshot that reproduces the result.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from commerce.models import Market
from core.models import ProductStore
from offers.models import Offer, OfferPriceObservation, StockStatus
from promotions.models import PromotionRevision, PurchaseRoute

from .domain.conditions import (
    DESTINATION_FACT,
    Amounts,
    ConditionInput,
    leaf_key,
)
from .domain.conditions import evaluate as evaluate_conditions
from .domain.engine import Inputs, canonical, evaluate, fingerprint
from .domain.types import (
    CartLine,
    CheckoutGroup,
    Claim,
    CompatibilityFact,
    Destination,
    EffectRule,
    FeeFact,
    OfferFact,
    Policy,
    PriceFact,
    PricingResult,
    PurchaseContext,
    RevisionRule,
    RewardTermsFact,
    RouteFact,
    ScopeRule,
    ShippingFact,
    Tri,
)
from .models import (
    CurrencyConversionQuote,
    PricingPolicyRevision,
    PricingQuote,
    QuoteLine,
    ShippingQuote,
    TaxFeeQuote,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

LEGACY_PRICE_ID = 0
EMPTY_AMOUNTS = Amounts(
    before_discounts=Decimal(0),
    after_item_discounts=Decimal(0),
    after_order_discounts=Decimal(0),
    shipping=None,
    quantity=0,
)
DEFAULT_FRESHNESS_HOURS = 72
POLICY_FIELDS = (
    "accepted_semantics",
    "accepted_evidence",
    "cash_methods",
    "include_unknown_payment",
    "allow_codes",
    "allow_private_codes",
    "allow_rewards",
    "allow_conditions",
    "net_cost_counts_money_rewards",
    "assume_full_caps",
    "max_combinations",
)


def policy_from(revision: PricingPolicyRevision) -> Policy:
    """Read a policy revision's typed rules; unknown keys are ignored."""
    rules = revision.rules or {}
    values: dict[str, object] = {}
    for name in POLICY_FIELDS:
        if name not in rules:
            continue
        value = rules[name]
        values[name] = frozenset(value) if isinstance(value, list) else value
    return Policy(
        key=revision.key,
        version=revision.number,
        scenario=revision.scenario,
        **values,
    )


def freshness(revision: PricingPolicyRevision) -> timedelta:
    """How long an observation stays usable after a read confirmed it."""
    hours = (revision.rules or {}).get("freshness_hours", DEFAULT_FRESHNESS_HOURS)
    return timedelta(hours=int(hours))


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
            prices=self.prices(ids, freshness(policy)),
            revisions=self.revisions(),
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
        facts: dict[int, OfferFact] = {}
        for offer in rows:
            variant = offer.listing_variant
            market = (
                variant.listing.market if variant else namespaces.get(offer.store_slug)
            )
            if market is None:
                continue
            product = links.get(offer.pk)
            categories: frozenset[int] = frozenset()
            if product is not None and product.category is not None:
                ancestors = product.category.get_ancestors()
                categories = frozenset(
                    [product.category.pk, *(node.pk for node in ancestors)],
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
        rows = (
            OfferPriceObservation.objects.filter(offer_id__in=ids)
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
                context=_context_pairs(row.context),
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
        return tuple(_rule(revision) for revision in newest.values())


def _context_pairs(context: object) -> tuple[tuple[str, str], ...]:
    """Flatten an observation's context into sorted, hashable pairs."""
    if not isinstance(context, dict):
        return ()
    return tuple(sorted((str(key), str(value)) for key, value in context.items()))


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


@dataclass(frozen=True)
class QuoteRequest:
    """What a caller asks: these lines, under this policy, in this context."""

    lines: tuple[CartLine, ...]
    policy: PricingPolicyRevision
    context: dict[str, object] | None = None


class PricingService:
    """Evaluate scenarios against stored facts, and keep quotes when asked."""

    def __init__(self, loader: FactLoader | None = None) -> None:
        """Use the given loader, or the database one."""
        self.loader = loader or FactLoader()

    def inputs(self, request: QuoteRequest, now: datetime | None = None) -> Inputs:
        """Build the engine's inputs for one request."""
        moment = now or timezone.now()
        facts = self.loader.load(
            (line.offer_id for line in request.lines),
            request.policy,
        )
        first = facts.offers.get(request.lines[0].offer_id) if request.lines else None
        market = Market.objects.select_related("currency").get(
            pk=first.market_id if first else request.policy.market_id,
        )
        extra = dict(request.context or {})
        context = PurchaseContext(
            now=moment,
            market_id=market.pk,
            currency=market.currency_id,
            minor_unit=market.currency.minor_unit,
            lines=request.lines,
            **extra,
        )
        if not context.groups:
            # One checkout of every line, named like the shipping quotes are.
            context = replace(
                context,
                groups=(
                    CheckoutGroup(
                        key=group_fingerprint(request.lines, context.destination),
                        offer_ids=frozenset(line.offer_id for line in request.lines),
                    ),
                ),
            )
        shipping, fees = quoted_costs(
            [group.key for group in context.groups],
            moment,
        )
        return Inputs(
            context=context,
            offers=tuple(facts.offers.values()),
            prices=facts.prices,
            revisions=facts.revisions,
            policy=policy_from(request.policy),
            routes=facts.routes,
            shipping=shipping,
            fees=fees,
            fees_status=(
                "included_in_prices"
                if market.tax_inclusion == "included"
                else ("consulted" if fees else "not_consulted")
            ),
        )

    def evaluate(
        self, request: QuoteRequest, now: datetime | None = None
    ) -> PricingResult:
        """Evaluate one request without persisting anything."""
        return evaluate(self.inputs(request, now))

    @transaction.atomic
    def quote(self, request: QuoteRequest, now: datetime | None = None) -> PricingQuote:
        """Evaluate and keep a quote whose snapshot reproduces the result."""
        inputs = self.inputs(request, now)
        result = evaluate(inputs)
        protected = _private_safe(inputs)
        quote = PricingQuote.objects.create(
            policy=request.policy,
            market_id=inputs.context.market_id,
            currency_id=inputs.context.currency,
            input_fingerprint=result.input_fingerprint,
            engine_version=result.engine_version,
            snapshot={
                "inputs": canonical(protected),
                "result": canonical(result),
                "protected_fingerprint": fingerprint(protected),
            },
            merchandise_total=result.merchandise_total,
            total_payable=result.total_payable,
            evaluated_at=result.evaluated_at,
            expires_at=result.expires_at,
        )
        quote.revisions.set(
            PromotionRevision.objects.filter(pk__in=[r.id for r in inputs.revisions]),
        )
        quote.observations.set(
            OfferPriceObservation.objects.filter(
                pk__in=[p.observation_id for p in result.selected_prices],
            ),
        )
        discounts = _discounts_by_offer(result)
        selected = {price.offer_id: price for price in result.selected_prices}
        QuoteLine.objects.bulk_create(
            QuoteLine(
                quote=quote,
                offer_id=line.offer_id,
                quantity=line.quantity,
                base_amount=(
                    selected[line.offer_id].amount
                    if line.offer_id in selected
                    else None
                ),
                allocated_discount=discounts.get(line.offer_id, Decimal(0)),
            )
            for line in result.lines
            if line.offer_id in inputs_offers(inputs)
        )
        return quote


def group_fingerprint(
    lines: tuple[CartLine, ...],
    destination: Destination | None,
) -> str:
    """Name a checkout group by its lines and destination, never in clear.

    Shipping depends on what is shipped and where: quantity and offers are
    part of the key, the postal code only as a keyed token.
    """
    parts = sorted(f"{line.offer_id}x{line.quantity}" for line in lines)
    place = ""
    if destination is not None:
        place = "|".join(
            (
                destination.country,
                destination.subdivision,
                _token(destination.postal_code) if destination.postal_code else "",
            ),
        )
    text = ";".join(parts) + "@" + place
    return hashlib.sha256(text.encode()).hexdigest()


def quoted_costs(
    group_keys: list[str],
    now: datetime,
) -> tuple[tuple[ShippingFact, ...], tuple[FeeFact, ...]]:
    """Return the shipping and fees quoted for these groups, still valid."""
    shipping = tuple(
        ShippingFact(
            group_key=quote.group_fingerprint,
            amount=quote.amount,
            currency=quote.currency_id,
            modality=quote.modality,
            estimate_days=quote.estimate_days,
            included_benefits=tuple(quote.included_benefits or ()),
        )
        for quote in ShippingQuote.objects.filter(
            group_fingerprint__in=group_keys,
            expires_at__gt=now,
        ).order_by("group_fingerprint", "amount", "-observed_at")
    )
    cheapest: dict[str, ShippingFact] = {}
    for fact in shipping:
        cheapest.setdefault(fact.group_key, fact)
    fees = tuple(
        FeeFact(
            group_key=quote.group_fingerprint,
            kind=quote.kind,
            amount=quote.amount,
            currency=quote.currency_id,
            included_in_price=quote.inclusion == "included",
        )
        for quote in TaxFeeQuote.objects.filter(
            group_fingerprint__in=group_keys,
            expires_at__gt=now,
        )
    )
    return tuple(cheapest.values()), fees


def inputs_offers(inputs: Inputs) -> set[int]:
    """Return the ids of the offers an evaluation was given."""
    return {offer.id for offer in inputs.offers}


def _discounts_by_offer(result: PricingResult) -> dict[int, Decimal]:
    totals: dict[int, Decimal] = {}
    for adjustment in result.adjustments:
        for offer_id, amount in adjustment.allocations:
            totals[offer_id] = totals.get(offer_id, Decimal(0)) + amount
    return totals


def _private_safe(inputs: Inputs) -> Inputs:
    """Return inputs a quote may keep, which still reproduce its result.

    Codes become the same keyed token on both sides, so a code a buyer
    entered still matches the code a revision names, and neither is stored
    in clear. The postal code is replaced by a token after every destination
    leaf was evaluated with it; those outcomes travel as facts with their
    provenance, so a replay reaches the same decision without the address.
    """
    context = inputs.context
    facts = tuple(_destination_facts(inputs))
    destination = context.destination
    if destination is not None and destination.postal_code:
        destination = replace(destination, postal_code=_token(destination.postal_code))
    revisions = tuple(
        replace(
            revision,
            codes=tuple(
                (kind, _token(code) if code else code) for kind, code in revision.codes
            ),
        )
        for revision in inputs.revisions
    )
    return replace(
        inputs,
        context=replace(
            context,
            destination=destination,
            codes=frozenset(_token(code) for code in context.codes),
            claims=(*context.claims, *facts),
        ),
        revisions=revisions,
    )


def _destination_facts(inputs: Inputs) -> list[Claim]:
    """Evaluate every destination leaf with the real destination, as facts."""
    facts: dict[str, Claim] = {}
    for revision in inputs.revisions:
        for leaf in _leaves_of_kind(revision.conditions.get("root"), "destination"):
            outcome = evaluate_conditions(
                {"root": leaf},
                ConditionInput(
                    context=inputs.context,
                    revision=revision,
                    offers=inputs.offers,
                    qualifying=EMPTY_AMOUNTS,
                    order=EMPTY_AMOUNTS,
                ),
            ).value
            if outcome is not Tri.UNKNOWN:
                key = leaf_key(leaf)
                facts[key] = Claim(
                    kind=DESTINATION_FACT,
                    issuer=key,
                    value=outcome is Tri.TRUE,
                    provenance="evaluated_before_protection",
                )
    return list(facts.values())


def _leaves_of_kind(node: object, kind: str) -> list[dict]:
    if not isinstance(node, dict):
        return []
    for combinator in ("all", "any"):
        if combinator in node:
            return [
                leaf
                for child in node[combinator]
                for leaf in _leaves_of_kind(child, kind)
            ]
    if "not" in node:
        return _leaves_of_kind(node["not"], kind)
    return [node] if node.get("kind") == kind else []


def _token(value: str) -> str:
    """Return a keyed token for a private value: equal values, equal tokens."""
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"token:{digest}"


__all__ = ["FactLoader", "PricingService", "QuoteRequest", "policy_from"]


@dataclass(frozen=True)
class DisplayAmount:
    """An amount shown in another currency, with the rate that converted it."""

    amount: Decimal
    currency: str
    rate_id: int
    rate: Decimal
    spread_known: bool


def convert_for_display(
    amount: Decimal,
    source: str,
    target: str,
    now: datetime,
) -> DisplayAmount | None:
    """Convert an amount for display with a valid rate, or return None.

    The seller still charges ``amount`` in ``source``. Without a rate valid at
    ``now`` there is no converted amount; a spread or fee left unknown stays
    unknown and is reported, not assumed zero.
    """
    if source == target:
        return None
    rate = (
        CurrencyConversionQuote.objects.filter(
            base_id=source,
            quote_id=target,
            observed_at__lte=now,
            valid_until__gt=now,
        )
        .order_by("-observed_at")
        .first()
    )
    if rate is None:
        return None
    return DisplayAmount(
        amount=amount * rate.rate,
        currency=target,
        rate_id=rate.pk,
        rate=rate.rate,
        spread_known=rate.spread is not None,
    )
