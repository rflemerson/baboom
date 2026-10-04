"""SYNTHETIC: the launch switch keeps prices until a market is ready."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from common.testing import raised
from core.models import Product, ProductStore
from offers.models import Offer, StockStatus
from pricing.models import OfferScenarioProjection
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import URL, TwoProductCatalog


class CutoverTests(TwoProductCatalog, TestCase):
    """Before the switch, the last read price; after it, projections."""

    def _prices(self) -> dict[str, str | None]:
        items = self.client.get(URL).json()["items"]
        return {item["name"]: item["price"] for item in items}

    @override_settings(PRICING_PROJECTION_COUNTRIES=[])
    def test_an_unswitched_market_keeps_its_prices_before_any_projection(
        self,
    ) -> None:
        """Deploying changes nothing a buyer sees until the market switches."""
        payload = self.client.get(URL).json()

        assert self._prices() == {"A": "100.00", "B": "120.00"}
        assert payload["scenario"] == {"key": "current", "version": None}

    def test_a_switched_market_reads_projections(self) -> None:
        """After the switch, only projected prices rank."""
        assert self._prices() == {"A": None, "B": None}

        ProjectionService().refresh()

        assert self._prices() == {"A": "100.00", "B": "120.00"}


class CoverageReportTests(TwoProductCatalog, TestCase):
    """The report names what switching a market would lose, and why."""

    def test_a_stale_price_is_reported_as_lost(self) -> None:
        """B was read long ago: priced today, refused by projections as stale."""
        ProjectionService().refresh()
        OfferScenarioProjection.objects.filter(offer=self.offers["B"]).update(
            status=OfferScenarioProjection.Status.NO_PRICE,
            amount=None,
            comparison_amount=None,
            explanation={"refusals": ["price 9: stale (past its freshness)"]},
        )
        out = StringIO()

        call_command("pricing_coverage", "--details", stdout=out)

        text = out.getvalue()
        assert "Priced today in BR/BRL: 2" in text
        assert "Policy normal: 1 priced, 1 priced today lose their price" in text
        assert "by reason: stale (past its freshness): 1" in text
        assert "B [store]: stale (past its freshness)" in text

    def _lose(self, offer: Offer, reason: str) -> None:
        OfferScenarioProjection.objects.filter(offer=offer).update(
            status=OfferScenarioProjection.Status.NO_PRICE,
            amount=None,
            comparison_amount=None,
            explanation={"refusals": [f"price 9: {reason}"]},
        )

    def test_the_gate_fails_only_when_a_price_is_lost(self) -> None:
        """Exit code: error with a loss, success when every price is kept."""
        ProjectionService().refresh()
        call_command("pricing_coverage", "--fail-on-loss", stdout=StringIO())
        self._lose(self.offers["B"], "stale (past its freshness)")

        error = raised(
            lambda: call_command(
                "pricing_coverage", "--fail-on-loss", stdout=StringIO()
            ),
            CommandError,
        )

        assert "lost by projections" in str(error)
        call_command("pricing_coverage", stdout=StringIO())

    def test_the_reason_is_that_of_the_offer_winning_today(self) -> None:
        """A has two offers; the R$ 90 one wins today and gives the reason."""
        other = Offer.objects.create(
            store_slug="store",
            external_id="A2",
            url="https://store.example/A2",
            current_price=Decimal("90.00"),
            current_stock_status=StockStatus.AVAILABLE,
            seller_account=self.seller,
        )
        ProductStore.objects.create(product=Product.objects.get(name="A"), offer=other)
        ProjectionService().refresh()
        self._lose(self.offers["A"], "unrelated refusal")
        self._lose(other, "stale (past its freshness)")
        out = StringIO()

        call_command("pricing_coverage", "--details", stdout=out)

        text = out.getvalue()
        assert "A [store]: stale (past its freshness)" in text
        assert "unrelated refusal" not in text

    def test_a_different_winner_or_link_is_reported(self) -> None:
        """The normal projection picks another offer for A and another link for B."""
        other = Offer.objects.create(
            store_slug="store",
            external_id="A2",
            url="https://store.example/A2",
            current_price=Decimal("90.00"),
            current_stock_status=StockStatus.AVAILABLE,
            seller_account=self.seller,
        )
        ProductStore.objects.create(product=Product.objects.get(name="A"), offer=other)
        ProjectionService().refresh()
        OfferScenarioProjection.objects.filter(
            offer=other, policy__key="normal"
        ).update(comparison_amount=Decimal(150), amount=Decimal(150))
        OfferScenarioProjection.objects.filter(
            offer=self.offers["B"], policy__key="normal"
        ).update(resolved_url="https://synthetic.example/route")
        out = StringIO()

        call_command("pricing_coverage", stdout=out)

        text = out.getvalue()
        assert "Divergences from the normal projection: 2" in text
        assert (
            f"A: offer {other.pk} wins today, {self.offers['A'].pk} projected" in text
        )
        assert (
            "B: link https://store.example/B today, https://synthetic.example/route"
            in text
        )

    def test_matching_prices_report_no_divergence(self) -> None:
        """Same winner and link: nothing to report."""
        ProjectionService().refresh()
        out = StringIO()

        call_command("pricing_coverage", stdout=out)

        assert "Divergences from the normal projection: 0" in out.getvalue()
