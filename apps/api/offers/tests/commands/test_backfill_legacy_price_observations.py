"""Legacy history is copied as legacy_unknown, never reinterpreted."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from commerce.tests.factories import MarketFactory
from offers.models import (
    Listing,
    ListingVariant,
    OfferPriceObservation,
    PaymentScope,
    PriceObservation,
)
from offers.tests.factories import OfferFactory


class BackfillLegacyPriceObservationTests(TestCase):
    """Preview first; copies are idempotent and keep their meaning unknown."""

    def setUp(self) -> None:
        """Create one identified offer with two legacy prices."""
        market = MarketFactory()
        variant = ListingVariant.objects.create(
            listing=Listing.objects.create(market=market, external_id="p"),
            external_id="v",
        )
        self.offer = OfferFactory(listing_variant=variant)
        for price in ("99.90", "89.90"):
            PriceObservation.objects.create(offer=self.offer, price=Decimal(price))
        PriceObservation.objects.create(offer=OfferFactory(), price=Decimal(10))

    def _run(self, *args: str) -> str:
        out = StringIO()
        call_command("backfill_legacy_price_observations", *args, stdout=out)
        return out.getvalue()

    def test_preview_copies_nothing(self) -> None:
        """The report counts; the database is unchanged."""
        output = self._run()

        assert "Would copy 2 observations." in output
        assert not OfferPriceObservation.objects.exists()

    def test_apply_copies_as_legacy_unknown(self) -> None:
        """No payment scope, method or composition is inferred."""
        output = self._run("--apply")

        rows = OfferPriceObservation.objects.filter(offer=self.offer)
        assert "Skipped, offer without a market: 1" in output
        assert {row.amount for row in rows} == {Decimal("99.90"), Decimal("89.90")}
        for row in rows:
            assert row.semantics == OfferPriceObservation.Semantics.LEGACY_UNKNOWN
            assert row.payment_scope == PaymentScope.UNKNOWN
            assert row.payment_method is None
            assert row.composition == OfferPriceObservation.Composition.UNKNOWN
            assert row.currency_id == "BRL"

    def test_applying_twice_copies_once(self) -> None:
        """The copy is idempotent."""
        self._run("--apply")
        output = self._run("--apply")

        assert "Copied 0 observations." in output
        assert (
            OfferPriceObservation.objects.count()
            == PriceObservation.objects.filter(
                offer=self.offer,
            ).count()
        )
