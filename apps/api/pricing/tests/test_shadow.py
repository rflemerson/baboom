"""The shadow comparison reports, and only reports, differences."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from common.testing import raised
from offers.models import Offer, OfferPriceObservation
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import TwoProductCatalog


class ShadowTests(TwoProductCatalog, TestCase):
    """The two-product catalog of the ranking tests, compared."""

    def _run(self, *args: str) -> str:
        out = StringIO()
        call_command("compare_pricing_shadow", *args, stdout=out)
        return out.getvalue()

    def test_equal_sources_report_no_difference(self) -> None:
        """Legacy and the listed policy agree before any promotion."""
        ProjectionService().refresh()

        output = self._run("--policy", "listed", "--strict")

        assert "2 equal, 0 different" in output

    def test_a_promotion_is_reported_as_an_amount_difference(self) -> None:
        """Projections see a promotion the legacy price cannot."""
        self._promote_b("30")
        ProjectionService().refresh()

        output = self._run("--policy", "listed")

        assert "amount: 1" in output
        assert "120.00 -> 84.00" in output

    def test_strict_mode_fails_on_a_difference(self) -> None:
        """A gate for the cutover."""
        self._promote_b("30")
        ProjectionService().refresh()

        raised(lambda: self._run("--policy", "listed", "--strict"), CommandError)

    def test_comparison_writes_nothing(self) -> None:
        """Read only."""
        ProjectionService().refresh()
        before = (Offer.objects.count(), OfferPriceObservation.objects.count())

        self._run()

        assert (Offer.objects.count(), OfferPriceObservation.objects.count()) == before
        assert Offer.objects.get(external_id="A").current_price == Decimal("100.00")
