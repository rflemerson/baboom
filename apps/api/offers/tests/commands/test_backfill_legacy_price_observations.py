"""Legacy history is copied as legacy_unknown, never reinterpreted."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from commerce.tests.factories import MarketFactory
from offers.models import (
    Listing,
    ListingVariant,
    Offer,
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


class LastReadConfirmationTests(TestCase):
    """The last crawl read the current price: it confirms the newest copy."""

    def setUp(self) -> None:
        """Create an offer whose price stopped changing a month ago."""
        market = MarketFactory()
        variant = ListingVariant.objects.create(
            listing=Listing.objects.create(market=market, external_id="p"),
            external_id="v",
        )
        self.read_at = timezone.now() - timedelta(hours=2)
        self.offer = OfferFactory(
            listing_variant=variant,
            current_price=Decimal("89.90"),
            last_seen_at=self.read_at,
        )
        for days, price in ((60, "99.90"), (30, "89.90")):
            PriceObservation.objects.create(
                offer=self.offer,
                price=Decimal(price),
                observed_at=timezone.now() - timedelta(days=days),
            )

    def _run(self, *args: str) -> str:
        out = StringIO()
        call_command("backfill_legacy_price_observations", *args, stdout=out)
        return out.getvalue()

    def _confirmed(self, amount: str) -> datetime:
        return OfferPriceObservation.objects.get(
            offer=self.offer, amount=Decimal(amount)
        ).confirmed_at

    def test_the_newest_copy_is_confirmed_at_the_last_read(self) -> None:
        """R$ 89.90 read two hours ago; R$ 99.90 keeps its age."""
        output = self._run("--apply")

        assert "Confirmed by the last crawl: 1" in output
        assert self._confirmed("89.90") == self.read_at
        assert self._confirmed("99.90") <= timezone.now() - timedelta(days=59)

    def test_a_different_current_price_confirms_nothing(self) -> None:
        """The crawl read another price: the copy is not what it saw."""
        Offer.objects.filter(pk=self.offer.pk).update(current_price=Decimal(80))

        output = self._run("--apply")

        assert "Confirmed by the last crawl: 0" in output
        assert self._confirmed("89.90") <= timezone.now() - timedelta(days=29)

    def test_a_delisted_offer_confirms_nothing(self) -> None:
        """A delisted offer was not read as for sale."""
        Offer.objects.filter(pk=self.offer.pk).update(delisted_at=timezone.now())

        output = self._run("--apply")

        assert "Confirmed by the last crawl: 0" in output

    def test_applying_twice_confirms_once(self) -> None:
        """A second run finds the copy already confirmed."""
        self._run("--apply")

        assert "Confirmed by the last crawl: 0" in self._run("--apply")
