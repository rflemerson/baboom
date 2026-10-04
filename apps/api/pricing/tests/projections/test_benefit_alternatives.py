"""SYNTHETIC: benefit filters, objectives and paging, through the database.

Every value is invented for the scenario; no real campaign is described.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.models import Product, ProductStore
from core.selectors import public_catalog_products
from offers.models import Evidence, Offer, StockStatus
from pricing.domain.types import CartLine
from pricing.models import OfferScenarioProjection, PricingPolicyRevision, ShippingQuote
from pricing.projections import ProjectionService
from pricing.selectors import BenefitFilter, projected_prices
from pricing.services import group_fingerprint
from pricing.tests.projections.test_projections import TwoProductCatalog
from promotions.models import (
    ActivationCode,
    Promotion,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
    RewardTerms,
)
from promotions.services import PromotionService


class BenefitCatalog(TwoProductCatalog):
    """A (R$ 100) and B (R$ 120), plus helpers to publish synthetic benefits."""

    def _publish(
        self,
        offer: Offer,
        kind: str,
        parameters: dict[str, object],
        *,
        code: str = "",
        reward_rate: Decimal | None = None,
    ) -> PromotionRevision:
        stage = "reward" if reward_rate is not None else "order"
        promotion = Promotion.objects.create(
            title=f"{kind} {offer.external_id} {code}",
            issuer_seller=self.seller,
            source_key=f"{kind}-{offer.pk}-{code}",
        )
        revision = PromotionRevision.objects.create(
            promotion=promotion,
            number=1,
            currency_id="BRL",
            timezone="America/Sao_Paulo",
            verified_at=timezone.now(),
            conditions={"root": {"kind": "code_required"}} if code else {"root": None},
        )
        PromotionScope.objects.create(
            revision=revision,
            role="target",
            kind="offer",
            ref_id=offer.pk,
        )
        effect = PromotionEffect.objects.create(
            revision=revision,
            position=1,
            kind=kind,
            stage=stage,
            basis="eligible_subtotal" if kind == "cashback" else "current",
            target="order",
            allocation="once",
            parameters=parameters,
        )
        if reward_rate is not None:
            RewardTerms.objects.create(
                effect=effect,
                credited_as="money",
                rate=reward_rate,
            )
        if code:
            ActivationCode.objects.create(
                revision=revision, kind="public_code", code=code
            )
        evidence = Evidence.objects.create(kind="announcement", excerpt="x")
        revision.evidence.add(evidence)
        with patch("pricing.receivers.refresh_projections.delay"):
            assert PromotionService().publish(revision, "executable").published
        return revision

    def _policy(self, key: str, **rules: object) -> PricingPolicyRevision:
        return PricingPolicyRevision.objects.create(
            key=key,
            number=1,
            scenario="listed",
            published_at=timezone.now(),
            rules={"freshness_hours": 72, **rules},
        )

    def _ranking(
        self,
        policy: PricingPolicyRevision,
        benefits: BenefitFilter | None = None,
    ) -> list[tuple[str, Decimal | None]]:
        source = projected_prices(
            policy,
            timezone.now(),
            country="BR",
            currency="BRL",
            benefits=benefits or BenefitFilter(),
        )
        rows = public_catalog_products(price_source=source).order_by(
            "comparison_price",
            "name",
        )
        return [(row.name, row.comparison_price) for row in rows]


class ObjectiveTests(BenefitCatalog, TestCase):
    """Paying R$ 90 now versus R$ 100 with R$ 20 back are different objectives."""

    def test_the_objective_picks_the_winner_and_keeps_both_values(self) -> None:
        """Items payable: B at 90. Estimated net cost: A at 80."""
        Offer.objects.filter(pk=self.offers["B"].pk).update(current_price=Decimal(100))
        self._publish(self.offers["B"], "fixed_amount", {"amount": "10"})
        self._publish(
            self.offers["A"],
            "cashback",
            {},
            reward_rate=Decimal(20),
        )
        payable = self._policy("payable", allow_rewards=True)
        net = self._policy(
            "net",
            allow_rewards=True,
            net_cost_counts_money_rewards=True,
            objective="estimated_net_cost",
        )
        unquoted = dict(self._ranking_after_refresh(net))
        self._free_shipping()
        ProjectionService().refresh()

        payable_ranking = self._ranking(payable)
        net_ranking = self._ranking(net)
        a_net = OfferScenarioProjection.objects.get(
            offer=self.offers["A"],
            policy=net,
            alternative="best",
        )

        # Without shipping the net cost is unknown, never zero.
        assert unquoted == {"A": None, "B": None}
        assert payable_ranking[0] == ("B", Decimal(90))
        assert net_ranking[0] == ("A", Decimal(80))
        assert a_net.amount == Decimal(100)
        assert a_net.monetary_reward == Decimal(20)
        assert a_net.estimated_net_cost == Decimal(80)

    def _ranking_after_refresh(
        self,
        policy: PricingPolicyRevision,
    ) -> list[tuple[str, Decimal | None]]:
        ProjectionService().refresh()
        return self._ranking(policy)

    def _free_shipping(self) -> None:
        """Quote free shipping for each offer alone; Brazilian prices hold taxes."""
        self.market.tax_inclusion = "included"
        self.market.save()
        for offer in self.offers.values():
            ShippingQuote.objects.create(
                group_fingerprint=group_fingerprint((CartLine(offer.pk, 1),), None),
                seller_account=self.seller,
                country="BR",
                postal_code_hash="",
                amount=Decimal(0),
                currency_id="BRL",
                source="synthetic",
                expires_at=timezone.now() + timedelta(hours=1),
            )


class CouponAlternativeTests(BenefitCatalog, TestCase):
    """A filter on a benefit finds the alternative, not only the default winner."""

    def setUp(self) -> None:
        """Product A also sells through a second offer, A2, at R$ 130."""
        super().setUp()
        self.a2 = Offer.objects.create(
            store_slug="store",
            external_id="A2",
            url="https://store.example/A2",
            current_price=Decimal(130),
            current_stock_status=StockStatus.AVAILABLE,
            seller_account=self.seller,
        )
        product = Product.objects.get(name="A")
        ProductStore.objects.create(product=product, offer=self.a2)
        self.policy = self._policy(
            "coupons",
            allow_codes=True,
            auto_public_codes=True,
            allow_rewards=True,
        )

    def test_the_coupon_offer_is_found_though_another_offer_wins(self) -> None:
        """A wins at 100; filtering for a coupon finds A2 at 110 with its code."""
        self._publish(self.a2, "fixed_amount", {"amount": "20"}, code="SYN20")
        ProjectionService().refresh()

        default = dict(self._ranking(self.policy))
        with_coupon = dict(self._ranking(self.policy, BenefitFilter(uses_coupon=True)))

        assert default["A"] == Decimal(100)
        assert with_coupon["A"] == Decimal(110)
        assert with_coupon["B"] is None

    def test_a_coupon_alternative_survives_a_better_offer_winner(self) -> None:
        """B wins with a 30% automatic discount; its 10-off coupon is still found."""
        self._promote_b("30")
        self._publish(self.offers["B"], "fixed_amount", {"amount": "10"}, code="SYN10")
        ProjectionService().refresh()

        best = OfferScenarioProjection.objects.get(
            offer=self.offers["B"],
            policy=self.policy,
            alternative="best",
        )
        coupon = dict(self._ranking(self.policy, BenefitFilter(uses_coupon=True)))

        assert best.comparison_amount == Decimal(84)
        assert not best.uses_coupon
        assert coupon["B"] == Decimal(110)

    def test_excluding_a_benefit_keeps_only_alternatives_without_it(self) -> None:
        """Without coupons, A2's coupon price never ranks."""
        self._publish(self.a2, "fixed_amount", {"amount": "50"}, code="SYN50")
        ProjectionService().refresh()

        ranking = dict(self._ranking(self.policy, BenefitFilter(uses_coupon=False)))

        assert ranking["A"] == Decimal(100)

    def test_a_small_page_keeps_the_global_order(self) -> None:
        """Filtering happens before choosing the winner and before paging."""
        self._publish(self.a2, "fixed_amount", {"amount": "40"}, code="SYN40")
        self._publish(self.offers["B"], "fixed_amount", {"amount": "5"}, code="SYN5")
        ProjectionService().refresh()
        source = projected_prices(
            self.policy,
            timezone.now(),
            country="BR",
            currency="BRL",
            benefits=BenefitFilter(uses_coupon=True),
        )
        full = [
            row.name
            for row in public_catalog_products(price_source=source).order_by(
                "comparison_price",
                "name",
            )
        ]
        paged = [
            row.name
            for start in range(len(full))
            for row in public_catalog_products(price_source=source).order_by(
                "comparison_price",
                "name",
            )[start : start + 1]
        ]

        assert full == ["A", "B"]
        assert paged == full


class PersonalBenefitTests(BenefitCatalog, TestCase):
    """A first-purchase benefit never enters a public ranking."""

    def test_an_undeclared_first_purchase_stays_out_of_public_prices(self) -> None:
        """Without a buyer's claim the condition is unknown; the public price holds."""
        revision = self._publish(self.offers["A"], "fixed_amount", {"amount": "30"})
        PromotionRevision.objects.filter(pk=revision.pk)  # published, frozen
        draft = PromotionService().revise(revision.promotion)
        draft.conditions = {
            "root": {
                "kind": "new_customer",
                "issuer": "seller",
                "issuer_id": self.seller.pk,
            },
        }
        draft.save()
        with patch("pricing.receivers.refresh_projections.delay"):
            assert PromotionService().publish(draft, "executable").published
        ProjectionService().refresh()

        ranking = dict(self._ranking(self.policy_for_public()))

        assert ranking["A"] == Decimal(100)

    def policy_for_public(self) -> PricingPolicyRevision:
        """Return the seeded public policy, which counts no buyer claim."""
        return PricingPolicyRevision.objects.get(key="listed", number=1)
