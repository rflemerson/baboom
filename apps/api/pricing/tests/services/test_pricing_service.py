"""The service prices stored facts and keeps reproducible quotes."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from commerce.models import Program
from common.testing import raised
from offers.models import Offer, PriceObservation, StockStatus
from pricing.costs import CostBook
from pricing.domain.types import CartLine, Claim
from pricing.groups import group_fingerprint
from pricing.models import (
    PricingPolicyRevision,
    PricingQuote,
    ShippingQuote,
    TaxFeeQuote,
)
from pricing.services import (
    PricingService,
    QuoteRequest,
)
from promotions.models import (
    PromotionEffect,
    PromotionScope,
    PurchaseRoute,
    RewardTerms,
)
from promotions.services import PromotionService
from promotions.tests.factories import first_purchase_draft
from scrapers.crawler.pipelines import CatalogPipeline
from scrapers.stores.max_titanium import MaxTitaniumSpider

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "scrapers/tests/fixtures/pricing/max_titanium.json"
)


def _ingest_max_titanium() -> Offer:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["payload"]
    raw = {
        "productId": payload["productId"],
        "productName": payload["productName"],
        "linkText": "whey",
        "items": [{"itemId": payload["itemId"], "sellers": payload["sellers"]}],
    }
    spider = MaxTitaniumSpider()
    for product in spider.process_raw_product(raw, "whey"):
        CatalogPipeline().process_item(product, spider)
    return Offer.objects.get()


SCENARIO_RULES: dict[str, dict[str, object]] = {
    "listed": {"accepted_semantics": ["known", "legacy_unknown"]},
    "cash": {
        "accepted_semantics": ["known"],
        "cash_methods": ["pix", "boleto"],
        "include_unknown_payment": False,
    },
}


def _policy(key: str) -> PricingPolicyRevision:
    """Return a seeded public policy, or a published one for a bare scenario."""
    if key not in SCENARIO_RULES:
        return PricingPolicyRevision.objects.get(key=key, number=1)
    policy, _created = PricingPolicyRevision.objects.get_or_create(
        key=f"scenario-{key}",
        number=1,
        defaults={
            "scenario": key,
            "rules": {"freshness_hours": 72, **SCENARIO_RULES[key]},
            "published_at": timezone.now(),
        },
    )
    return policy


class ScenarioTests(TestCase):
    """The seeded public policies price real observations."""

    def setUp(self) -> None:
        """Ingest the Max Titanium excerpt."""
        self.offer = _ingest_max_titanium()
        self.service = PricingService()

    def test_listed_scenario_is_the_store_price(self) -> None:
        """R$ 99.00 with no payment stated."""
        result = self.service.evaluate(
            QuoteRequest(lines=(CartLine(self.offer.pk),), policy=_policy("listed")),
        )

        assert result.merchandise_total == Decimal("99.00")

    def test_cash_scenario_is_the_pix_price(self) -> None:
        """R$ 96.03 by Pix, from the catalog's own payment options."""
        result = self.service.evaluate(
            QuoteRequest(lines=(CartLine(self.offer.pk),), policy=_policy("cash")),
        )

        assert result.merchandise_total == Decimal("96.03")
        assert result.selected_prices[0].payment_method == "pix"

    def test_a_sold_out_offer_has_no_price(self) -> None:
        """Availability is read from the offer."""
        Offer.objects.filter(pk=self.offer.pk).update(
            current_stock_status=StockStatus.OUT_OF_STOCK,
        )

        result = self.service.evaluate(
            QuoteRequest(lines=(CartLine(self.offer.pk),), policy=_policy("listed")),
        )

        assert result.merchandise_total is None


class LegacyTests(TestCase):
    """An offer with no typed observation keeps its legacy price, as unknown."""

    def test_legacy_price_counts_only_where_the_policy_accepts_it(self) -> None:
        """Listed accepts legacy_unknown; cash does not."""
        offer = _ingest_max_titanium()
        offer.price_points.all().delete()
        request = QuoteRequest(lines=(CartLine(offer.pk),), policy=_policy("listed"))

        listed = PricingService().evaluate(request)
        cash = PricingService().evaluate(
            QuoteRequest(lines=request.lines, policy=_policy("cash")),
        )

        assert listed.merchandise_total == Decimal("99.00")
        assert cash.merchandise_total is None


class QuoteTests(TestCase):
    """A personal scenario with a published coupon, kept as a quote."""

    def setUp(self) -> None:
        """Publish a 20% first-purchase coupon for the store's offers."""
        self.offer = _ingest_max_titanium()
        revision = first_purchase_draft()
        seller = self.offer.seller_account
        revision.promotion.issuer_seller = seller
        revision.promotion.save()
        PromotionScope.objects.filter(revision=revision).update(ref_id=seller.pk)
        revision.conditions["root"]["all"][1]["issuer_id"] = seller.pk
        revision.conditions["root"]["all"][2]["amount"] = "50"
        revision.save()
        assert PromotionService().publish(revision, "executable").published
        self.revision = revision
        self.policy = PricingPolicyRevision.objects.create(
            key="personal",
            number=1,
            scenario="listed",
            rules={
                "allow_codes": True,
                "allow_conditions": ["min_amount", "new_customer"],
            },
        )

    def _request(self) -> QuoteRequest:
        return QuoteRequest(
            lines=(CartLine(self.offer.pk),),
            policy=self.policy,
            context={
                "codes": frozenset({"PRIMEIRACOMPRA"}),
                "claims": (
                    Claim("new_customer", "seller", self.offer.seller_account_id),
                ),
            },
        )

    def test_the_coupon_applies_with_code_and_claim(self) -> None:
        """20% off R$ 99.00."""
        result = PricingService().evaluate(self._request())

        assert result.merchandise_total == Decimal("79.20")
        assert result.applied_revisions == (self.revision.pk,)

    def test_a_quote_keeps_a_snapshot_without_the_code_in_clear(self) -> None:
        """The snapshot reproduces the result; the code is hashed."""
        quote = PricingService().quote(self._request())

        codes = quote.snapshot["inputs"]["context"]["codes"]
        assert quote.merchandise_total == Decimal("79.20")
        assert codes
        assert all(code.startswith("token:") for code in codes)
        assert quote.revisions.get() == self.revision
        assert quote.lines.get().allocated_discount == Decimal("19.80")
        assert quote.snapshot["result"]["input_fingerprint"] == quote.input_fingerprint

    def test_a_quote_is_immutable(self) -> None:
        """A kept quote is never rewritten."""
        quote = PricingService().quote(self._request())
        quote.engine_version = "changed"

        raised(quote.save, ValueError)
        assert PricingQuote.objects.get().engine_version != "changed"


class LegacyAndTypedTests(TestCase):
    """Once an offer has typed observations, its legacy history stops counting."""

    def test_an_old_legacy_price_never_undercuts_a_typed_one(self) -> None:
        """A lower price from the migrated history is not today's price."""
        offer = _ingest_max_titanium()
        call_command("backfill_legacy_price_observations", "--apply", stdout=StringIO())
        PriceObservation.objects.create(offer=offer, price=Decimal("50.00"))
        call_command("backfill_legacy_price_observations", "--apply", stdout=StringIO())

        result = PricingService().evaluate(
            QuoteRequest(lines=(CartLine(offer.pk),), policy=_policy("listed")),
        )

        assert result.merchandise_total == Decimal("99.00")


class StoredRouteTests(TestCase):
    """R06: routes curated in the database reach the engine and the quote."""

    def test_a_curated_activation_route_enables_tracked_cashback(self) -> None:
        """Without the route nothing; with it, the reward and the route."""
        offer = _ingest_max_titanium()
        revision = first_purchase_draft()
        program = Program.objects.create(
            name="Cashback X",
            kind=Program.Kind.CASHBACK,
            issuer_name="X",
            unit="BRL",
        )
        PromotionScope.objects.filter(revision=revision).update(
            kind="offer",
            ref_id=offer.pk,
        )
        revision.conditions = {"root": None}
        revision.codes.all().delete()
        revision.effects.all().delete()
        revision.save()
        cashback = PromotionEffect.objects.create(
            revision=revision,
            position=1,
            kind="cashback",
            stage="reward",
            basis="eligible_subtotal",
            target="order",
            allocation="once",
        )
        RewardTerms.objects.create(
            effect=cashback,
            credited_as="money",
            rate=Decimal(10),
            tracking_required=True,
            program=program,
        )
        assert PromotionService().publish(revision, "executable").published
        rewards = PricingPolicyRevision.objects.create(
            key="rewards",
            number=1,
            scenario="listed",
            rules={"allow_rewards": True},
        )
        request = QuoteRequest(lines=(CartLine(offer.pk),), policy=rewards)

        without = PricingService().evaluate(request)
        PurchaseRoute.objects.create(
            offer=offer,
            kind="cashback_activation",
            program=program,
            url="https://cashback.example/go",
            fixes_variant=True,
        )
        with_route = PricingService().evaluate(request)

        assert without.deferred_rewards == ()
        assert with_route.deferred_rewards[0].amount == Decimal("9.90")
        assert with_route.purchase_routes[0].url == "https://cashback.example/go"


class PricelessQuoteTests(TestCase):
    """R11: a scenario without a price is a quote, not an exception."""

    def test_an_unavailable_offer_is_quoted_without_a_price(self) -> None:
        """The quote keeps the line, with no base amount."""
        offer = _ingest_max_titanium()
        Offer.objects.filter(pk=offer.pk).update(
            current_stock_status=StockStatus.OUT_OF_STOCK,
        )

        quote = PricingService().quote(
            QuoteRequest(lines=(CartLine(offer.pk),), policy=_policy("listed")),
        )

        assert quote.total_payable is None
        line = quote.lines.get()
        assert line.base_amount is None
        assert line.allocated_discount == 0


class StoredCostTests(TestCase):
    """Quoted shipping and taxes stored in the database reach the total."""

    def test_a_stored_shipping_quote_completes_the_total(self) -> None:
        """Brazilian prices include taxes; a valid shipping quote adds R$ 12."""
        offer = _ingest_max_titanium()
        request = QuoteRequest(lines=(CartLine(offer.pk),), policy=_policy("listed"))
        without = PricingService().evaluate(request)
        ShippingQuote.objects.create(
            group_fingerprint=group_fingerprint(request.lines, None),
            seller_account=offer.seller_account,
            country="BR",
            postal_code_hash="",
            amount=Decimal("12.00"),
            currency_id="BRL",
            source="test",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        with_shipping = PricingService().evaluate(request)

        assert without.total_payable is None
        assert with_shipping.shipping_total == Decimal("12.00")
        assert with_shipping.total_payable == Decimal("111.00")

    def test_a_market_of_unknown_taxes_has_no_total(self) -> None:
        """Without the market's tax fact, taxes are unknown, not zero."""
        offer = _ingest_max_titanium()
        market = offer.listing_variant.listing.market
        market.tax_inclusion = "unknown"
        market.save()
        request = QuoteRequest(lines=(CartLine(offer.pk),), policy=_policy("listed"))
        ShippingQuote.objects.create(
            group_fingerprint=group_fingerprint(request.lines, None),
            seller_account=offer.seller_account,
            country="BR",
            postal_code_hash="",
            amount=Decimal("12.00"),
            currency_id="BRL",
            source="test",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        result = PricingService().evaluate(request)

        assert result.total_payable is None
        assert "whether prices include taxes is unknown" in result.missing_context


class FeeStatusTests(TestCase):
    """A04: what is known about taxes and fees, in five distinct states."""

    def test_one_covered_group_does_not_cover_another(self) -> None:
        """A complete reading of group one says nothing about group two."""
        book = CostBook(
            shipping={},
            fees={"one": [self._fee(group_fingerprint="one", covers_all_charges=True)]},
        )

        _shipping, _fees, status = book.for_groups(["one", "two"], "unknown")

        assert status == "partial"

    def test_every_group_covered_is_consulted(self) -> None:
        """Both groups read completely: the sum is known."""
        fees = {
            key: [self._fee(group_fingerprint=key, covers_all_charges=True)]
            for key in ("one", "two")
        }

        _shipping, _fees, status = CostBook(shipping={}, fees=fees).for_groups(
            ["one", "two"],
            "unknown",
        )

        assert status == "consulted"

    def _fee(self, **values: object) -> TaxFeeQuote:
        base = {
            "group_fingerprint": "g",
            "kind": "service",
            "currency_id": "BRL",
            "inclusion": "excluded",
            "source": "synthetic",
            "expires_at": timezone.now() + timedelta(hours=1),
        }
        return TaxFeeQuote.objects.create(**{**base, **values})

    def _status(self, tax_inclusion: str) -> tuple[str, Decimal]:
        _shipping, fees, status = CostBook.load(["g"], timezone.now()).for_groups(
            ["g"],
            tax_inclusion,
        )
        return status, sum((fee.amount or 0 for fee in fees), Decimal(0))

    def test_each_state(self) -> None:
        """Included, not consulted, unknown, partial, then complete."""
        assert self._status("included")[0] == "included_in_prices"
        assert self._status("excluded")[0] == "not_consulted"
        assert self._status("unknown")[0] == "inclusion_unknown"
        self._fee(amount=5)
        assert self._status("excluded")[0] == "partial"
        self._fee(amount=3, charge_key="other", covers_all_charges=True)
        assert self._status("excluded") == ("consulted", Decimal(8))

    def test_a_confirmed_absence_of_fees_is_zero(self) -> None:
        """A reading that covered everything and found nothing."""
        self._fee(kind="none", amount=0, covers_all_charges=True)

        assert self._status("excluded") == ("consulted", Decimal(0))
