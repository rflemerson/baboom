"""R01/R02: which observation stands, through changes, withdrawals and migration."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from offers.models import PriceObservation, StockStatus
from offers.observations import ObservationService, PriceRead, PriceRecord, PriceSubject
from pricing.facts import FactLoader
from pricing.tests.services.test_pricing_service import _ingest_max_titanium

WINDOW = timedelta(hours=72)
FIELD = "review.pix"


class VigencyTests(TestCase):
    """The newest read of a condition decides whether it stands."""

    def setUp(self) -> None:
        """One identified offer and a clock that moves one second per read."""
        self.offer = _ingest_max_titanium()
        self.market = self.offer.listing_variant.listing.market
        self.service = ObservationService()
        self.moment = timezone.now()

    def _read(self, *amounts: str, complete: bool = True) -> None:
        self.moment += timedelta(seconds=1)
        batch = self.service.open_batch(
            self.market,
            adapter="test",
            adapter_version="1",
        )
        prices = tuple(
            PriceRecord(
                role="payable",
                amount=Decimal(amount),
                source_field=FIELD,
                payment_scope="method",
                payment_method="pix",
            )
            for amount in amounts
        )
        self.service.record_prices(
            batch,
            PriceSubject(self.offer, None),
            PriceRead(prices, complete=complete, observed_at=self.moment),
        )

    def _standing(self) -> list[Decimal]:
        facts = FactLoader.prices([self.offer.pk], WINDOW)
        return [fact.amount for fact in facts if fact.source_field == FIELD]

    def test_a_change_keeps_only_the_newest_value(self) -> None:
        """90 then 80: 80 stands."""
        self._read("90")
        self._read("80")

        assert self._standing() == [Decimal(80)]

    def test_a_withdrawal_removes_every_version(self) -> None:
        """90, 80, then absent from a complete read: nothing stands."""
        self._read("90")
        self._read("80")
        self._read()

        assert self._standing() == []

    def test_a_partial_read_withdraws_nothing(self) -> None:
        """Absent from a partial read: 80 still stands."""
        self._read("80")
        self._read(complete=False)

        assert self._standing() == [Decimal(80)]

    def test_withdrawing_twice_changes_nothing(self) -> None:
        """A second complete read without it keeps it gone."""
        self._read("80")
        self._read()
        self._read()

        assert self._standing() == []

    def test_a_condition_can_legitimately_come_back(self) -> None:
        """Withdrawn, then stated again at 85: 85 stands."""
        self._read("80")
        self._read()
        self._read("85")

        assert self._standing() == [Decimal(85)]

    def test_a_withdrawn_condition_never_falls_back_to_legacy(self) -> None:
        """An offer with typed history is not priced by its legacy price."""
        self.offer.price_points.exclude(source_field=FIELD).delete()
        self._read("80")
        self._read()

        assert FactLoader.prices([self.offer.pk], WINDOW) == ()


class LegacyFreshnessTests(TestCase):
    """R02: migrated history is as old as it was observed."""

    def test_old_history_is_stale_even_after_a_second_backfill(self) -> None:
        """A 30-day-old price never becomes fresh by being migrated."""
        offer = _ingest_max_titanium()
        offer.price_points.all().delete()
        PriceObservation.objects.filter(offer=offer).delete()
        old = timezone.now() - timedelta(days=30)
        PriceObservation.objects.create(
            offer=offer,
            price=Decimal(1),
            stock_status=StockStatus.AVAILABLE,
            observed_at=old,
        )
        for _ in range(2):
            call_command(
                "backfill_legacy_price_observations",
                "--apply",
                stdout=StringIO(),
            )

        facts = FactLoader.prices([offer.pk], WINDOW)
        assert facts
        assert all(fact.fresh_until <= timezone.now() for fact in facts)
