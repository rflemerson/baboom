"""The external review's reproductions (R01-R12), kept as executable checks.

Each test is the reviewer's case, adapted only where an interface changed
(``projected_prices`` now takes the market it ranks).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from commerce.services import CommerceIdentityService, MarketRef, SellerRef
from core.selectors import public_catalog_products
from offers.models import Offer, OfferPriceObservation, PriceObservation, StockStatus
from offers.observations import ObservationService, PriceRead, PriceRecord, PriceSubject
from pricing.domain.engine import evaluate
from pricing.domain.types import CartLine, RewardTermsFact
from pricing.models import OfferScenarioProjection
from pricing.projections import ProjectionService
from pricing.selectors import projected_prices
from pricing.services import FactLoader, PricingService, QuoteRequest, _private_safe
from pricing.tests.domain.builders import (
    context,
    effect,
    inputs,
    offer,
    policy,
    price,
    revision,
)
from pricing.tests.projections.test_projections import TwoProductCatalog
from pricing.tests.services.test_pricing_service import _ingest_max_titanium, _policy
from scrapers.stores.max_titanium import MaxTitaniumSpider
from scrapers.tests.services.test_typed_observations import _payload, _save, _vtex_raw

WINDOW = timedelta(hours=72)


class StoredFactsReview(TestCase):
    """R01, R02, R03, R04 and R11 on stored facts."""

    def setUp(self) -> None:
        """Ingest the real Max Titanium excerpt."""
        self.offer = _ingest_max_titanium()
        self.market = self.offer.listing_variant.listing.market

    def test_withdrawn_condition_cannot_resurrect_older_value(self) -> None:
        """R01: 90, 80, then absent: nothing stands."""
        service = ObservationService()
        subject = PriceSubject(self.offer, None)
        now = timezone.now()
        for index, values in enumerate((("90",), ("80",), ())):
            batch = service.open_batch(
                self.market, adapter="review", adapter_version="1"
            )
            points = tuple(
                PriceRecord(
                    role="payable",
                    amount=Decimal(value),
                    source_field="review.pix",
                    payment_scope="method",
                    payment_method="pix",
                )
                for value in values
            )
            service.record_prices(
                batch,
                subject,
                PriceRead(
                    points, complete=True, observed_at=now + timedelta(seconds=index)
                ),
            )
        loaded = FactLoader.prices([self.offer.pk], WINDOW)
        assert not [p for p in loaded if p.source_field == "review.pix"], loaded

    def test_price_minimum_quantity_must_be_enforced(self) -> None:
        """R04: a ten-unit price is not one unit's price."""
        OfferPriceObservation.objects.create(
            offer=self.offer,
            role="payable",
            amount=Decimal(1),
            currency_id="BRL",
            source_field="bulk",
            condition_key="bulk",
            quantity_min=10,
        )
        result = PricingService().evaluate(
            QuoteRequest((CartLine(self.offer.pk, 1),), _policy("listed")),
        )
        assert result.merchandise_total == Decimal(99), result.merchandise_total

    def test_unavailable_quote_can_be_persisted(self) -> None:
        """R11: an unavailable offer is a quote without a price."""
        Offer.objects.filter(pk=self.offer.pk).update(
            current_stock_status=StockStatus.OUT_OF_STOCK,
        )
        quote = PricingService().quote(
            QuoteRequest((CartLine(self.offer.pk),), _policy("listed")),
        )
        assert quote.total_payable is None

    def test_legacy_import_does_not_refresh_old_prices(self) -> None:
        """R02: a 30-day-old price stays stale after the backfill."""
        self.offer.price_points.all().delete()
        PriceObservation.objects.filter(offer=self.offer).delete()
        old = timezone.now() - timedelta(days=30)
        PriceObservation.objects.create(
            offer=self.offer,
            price=Decimal(1),
            stock_status=StockStatus.AVAILABLE,
            observed_at=old,
        )
        call_command("backfill_legacy_price_observations", "--apply", stdout=StringIO())
        points = FactLoader.prices([self.offer.pk], WINDOW)
        assert all(p.fresh_until <= timezone.now() for p in points), points

    def test_seller_collision_must_not_overwrite_price(self) -> None:
        """R03: the third-party offer keeps its R$ 250."""
        other = CommerceIdentityService.seller(
            self.market,
            SellerRef(external_id="legacy-third-party"),
        )
        Offer.objects.filter(pk=self.offer.pk).update(
            seller_account=other,
            current_price=Decimal(250),
        )
        spider = MaxTitaniumSpider()
        _save(
            spider,
            spider.process_raw_product(
                _vtex_raw(_payload("max_titanium")["sellers"]), "w"
            ),
        )
        self.offer.refresh_from_db()
        assert self.offer.current_price == Decimal(250), self.offer.current_price


class CurrencyReview(TwoProductCatalog, TestCase):
    """R05 at the selector."""

    def test_global_policy_must_not_compare_nominal_currencies(self) -> None:
        """A projection in MXN 1 never prices the Brazilian catalog."""
        mexico = CommerceIdentityService.market(
            MarketRef(
                namespace="mexico",
                channel_name="Mexico",
                channel_kind="independent_store",
                adapter="feed",
                country="MX",
                currency="MXN",
                timezone="America/Mexico_City",
            ),
        )
        ProjectionService().refresh()
        OfferScenarioProjection.objects.filter(
            offer=self.offers["B"],
            policy=_policy("listed"),
        ).update(market=mexico, currency_id="MXN", amount=Decimal(1))
        rows = list(
            public_catalog_products(
                price_source=projected_prices(
                    _policy("listed"),
                    timezone.now(),
                    country="BR",
                    currency="BRL",
                ),
            ),
        )
        assert not any(r.name == "B" and r.price == Decimal(1) for r in rows)


class EngineReview(SimpleTestCase):
    """R06, R07, R08, R09 and R12 in the engine."""

    def test_tracking_cashback_requires_route(self) -> None:
        """R06: no activation route, no reward."""
        tracked = RewardTermsFact(
            credited_as="money",
            rate=Decimal(10),
            tracking_required=True,
        )
        result = evaluate(
            inputs(
                policy=policy(allow_rewards=True),
                revisions=(
                    revision(1, effect("cashback", stage="reward", reward=tracked)),
                ),
            ),
        )
        assert not any(x.amount is not None for x in result.deferred_rewards)

    def test_snapshot_preserves_public_coupon_result(self) -> None:
        """R08: the protected inputs give the same result."""
        rule = revision(
            1,
            effect("percentage", params={"rate": "20"}),
            codes=(("public_code", "PUBLIC20"),),
            conditions={"root": {"kind": "code_required"}},
        )
        data = inputs(
            context=context(codes=frozenset({"PUBLIC20"})),
            policy=policy(allow_codes=True),
            revisions=(rule,),
        )
        assert (
            evaluate(_private_safe(data)).merchandise_total
            == evaluate(data).merchandise_total
        )

    def test_multibuy_respects_cap(self) -> None:
        """R09: buy 3 pay 2 capped at R$ 10."""
        result = evaluate(
            inputs(
                context=context(CartLine(1, 3)),
                revisions=(
                    revision(
                        1,
                        effect(
                            "multibuy", params={"buy": 3, "pay": 2}, cap=Decimal(10)
                        ),
                    ),
                ),
            ),
        )
        assert result.merchandise_total == Decimal(290), result.merchandise_total

    def test_mixed_payment_discount_not_applied_twice(self) -> None:
        """R07: only the line without an included discount gets it."""
        result = evaluate(
            inputs(
                context=context(CartLine(1), CartLine(2)),
                offers=(offer(1), offer(2)),
                prices=(
                    price(1, "90", included_adjustments=("payment_discount",)),
                    price(2, "100"),
                ),
                revisions=(
                    revision(
                        1, effect("percentage", stage="payment", params={"rate": "10"})
                    ),
                ),
            ),
        )
        assert result.merchandise_total == Decimal(180), result.merchandise_total

    def test_any_payment_is_a_valid_listed_price(self) -> None:
        """R12: a price for any payment is the store's price."""
        result = evaluate(inputs(prices=(price(1, "100", payment_scope="any"),)))
        assert result.merchandise_total == Decimal(100), result.merchandise_total
