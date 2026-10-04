"""SYNTHETIC: the launch switch keeps prices until a market is ready."""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

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
