"""Projections price every linked offer; the catalog ranks them before paginating."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from commerce.services import CommerceIdentityService, MarketRef, SellerRef
from core.models import Brand, Product, ProductStore, Store
from offers.models import Evidence, Offer, StockStatus
from pricing.models import OfferScenarioProjection, PricingPolicyRevision
from pricing.projections import ProjectionService
from promotions.models import (
    Promotion,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
)
from promotions.services import PromotionService

URL = "/api/catalog/products/"


class RankingTests(TestCase):
    """Two products; the cheaper raw price can lose to a promotion."""

    def setUp(self) -> None:
        """Product A at R$ 100, product B at R$ 120, one store."""
        self.market = CommerceIdentityService.market(
            MarketRef(
                namespace="store",
                channel_name="Store",
                channel_kind="independent_store",
                adapter="shopify",
                country="BR",
                currency="BRL",
                timezone="America/Sao_Paulo",
            ),
        )
        self.seller = CommerceIdentityService.seller(
            self.market,
            SellerRef(is_channel_owner=True),
        )
        Store.objects.create(name="Store", display_name="Store", scraper_slug="store")
        brand = Brand.objects.create(name="b", display_name="B")
        self.offers = {}
        for name, price in (("A", "100.00"), ("B", "120.00")):
            product = Product.objects.create(name=name, brand=brand, is_published=True)
            offer = Offer.objects.create(
                store_slug="store",
                external_id=name,
                url=f"https://store.example/{name}",
                current_price=Decimal(price),
                current_stock_status=StockStatus.AVAILABLE,
                seller_account=self.seller,
            )
            ProductStore.objects.create(product=product, offer=offer)
            self.offers[name] = offer

    def _promote_b(self, rate: str, ends_at: object = None) -> PromotionRevision:
        """Publish an automatic discount on offer B."""
        promotion = Promotion.objects.create(
            title=f"B {rate}%",
            issuer_seller=self.seller,
            source_key=f"b-{rate}",
        )
        revision = PromotionRevision.objects.create(
            promotion=promotion,
            number=1,
            currency_id="BRL",
            timezone="America/Sao_Paulo",
            verified_at=timezone.now(),
            ends_at=ends_at,
        )
        PromotionScope.objects.create(
            revision=revision,
            role="target",
            kind="offer",
            ref_id=self.offers["B"].pk,
        )
        PromotionEffect.objects.create(
            revision=revision,
            position=1,
            kind="percentage",
            stage="catalog",
            basis="current",
            target="item",
            allocation="per_line",
            parameters={"rate": rate},
        )
        revision.evidence.add(Evidence.objects.create(kind="announcement", excerpt="B"))
        assert PromotionService().publish(revision, "executable").published
        return revision

    def _page(self, **params: str) -> dict:
        query = {"per_page": "12", "sort_by": "price", "sort_dir": "asc", **params}
        return json.loads(self.client.get(URL, query).content)

    def test_refresh_projects_every_linked_offer_under_every_policy(self) -> None:
        """Two offers, two seeded public policies."""
        written = ProjectionService().refresh()

        assert written == len(self.offers) * PricingPolicyRevision.objects.count()
        projection = OfferScenarioProjection.objects.get(
            offer=self.offers["A"],
            policy__key="listed",
        )
        assert projection.amount == Decimal("100.00")
        assert projection.status == "priced"

    def test_cash_scenario_has_no_price_without_a_cash_observation(self) -> None:
        """A legacy price says nothing about cash; it is not relabelled."""
        ProjectionService().refresh()

        projection = OfferScenarioProjection.objects.get(
            offer=self.offers["A"],
            policy__key="cash",
        )
        assert projection.status == "no_price"
        assert projection.amount is None

    def test_a_promoted_offer_wins_before_pagination(self) -> None:
        """B at R$ 120 with 30% off (R$ 84) ranks above A at R$ 100."""
        self._promote_b("30")
        ProjectionService().refresh()

        items = self._page(scenario="listed", per_page="12")["items"]

        assert [item["name"] for item in items] == ["B", "A"]
        assert Decimal(items[0]["price"]) == Decimal("84.00")

    def test_the_winner_links_to_its_own_offer(self) -> None:
        """Price and link come from the same projected offer."""
        self._promote_b("30")
        ProjectionService().refresh()

        response = self.client.get(
            URL,
            {"scenario": "listed", "per_page": "12", "sort_by": "price"},
        )
        first = json.loads(response.content)["items"][0]

        assert first["name"] == "B"
        assert first["externalLink"] == "https://store.example/B"

    def test_an_expired_promotion_leaves_the_ranking_at_read_time(self) -> None:
        """Expiry is checked when reading, even if a refresh is late."""
        self._promote_b("30", ends_at=timezone.now() + timedelta(minutes=5))
        ProjectionService().refresh()
        later = timezone.now() + timedelta(minutes=10)

        with patch("core.rest.views.timezone.now", return_value=later):
            items = self._page(scenario="listed")["items"]

        assert {item["name"]: item["price"] for item in items}["B"] is None

    def test_legacy_ranking_stays_until_the_cutover(self) -> None:
        """Without a scenario and with the switch off, legacy prices rank."""
        ProjectionService().refresh()

        payload = self._page()

        assert payload["scenario"]["source"] == "legacy"

    @override_settings(PRICING_READ_PROJECTIONS=True)
    def test_the_cutover_switch_reads_the_default_policy(self) -> None:
        """With the switch on, the default ranking reads projections."""
        self._promote_b("30")
        ProjectionService().refresh()

        payload = self._page()

        assert payload["scenario"] == {
            "key": "listed",
            "version": 1,
            "source": "projection",
        }
        assert payload["items"][0]["name"] == "B"

    def test_an_unknown_scenario_is_refused(self) -> None:
        """A typo is not silently the default."""
        response = self.client.get(URL, {"scenario": "cheapest-ever"})

        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_publishing_a_promotion_schedules_a_refresh(self) -> None:
        """Rules changed: projections are recomputed after commit."""
        with (
            patch("pricing.receivers.refresh_projections.delay") as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self._promote_b("10")

        delay.assert_called_with(None)
