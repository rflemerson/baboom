"""R01/R02: which observation stands, through changes, withdrawals and migration."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from offers.observations import ObservationService, PriceRead, PriceRecord, PriceSubject
from pricing.facts import FactLoader
from pricing.tests.services.test_pricing_service import _ingest_max_titanium

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
        facts = FactLoader.prices([self.offer.pk])
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

        assert FactLoader.prices([self.offer.pk]) == ()
