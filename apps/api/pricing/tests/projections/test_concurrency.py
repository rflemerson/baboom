"""SYNTHETIC, PostgreSQL only: concurrent refreshes never publish an older price."""

from __future__ import annotations

import threading
from datetime import timedelta

from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from commerce.models import Currency
from offers.models import Offer
from pricing.models import OfferScenarioProjection, PricingPolicyRevision
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import TwoProductCatalog

WAIT_SECONDS = 1.0


class ConcurrentRefreshTests(TwoProductCatalog, TransactionTestCase):
    """Row locks order refreshes; a refresh never replaces a newer one."""

    def setUp(self) -> None:
        """Run on PostgreSQL only: SQLite has no row locks.

        A TransactionTestCase empties the tables, seeded rows included, so
        the test recreates the currency and the policy it needs.
        """
        if connection.vendor != "postgresql":
            self.skipTest("Row locks exist on PostgreSQL only.")
        Currency.objects.get_or_create(code="BRL", defaults={"minor_unit": 2})
        super().setUp()
        PricingPolicyRevision.objects.get_or_create(
            key="concurrent",
            number=1,
            defaults={
                "scenario": "listed",
                "rules": {"freshness_hours": 72},
                "published_at": timezone.now(),
            },
        )

    def test_an_older_refresh_never_replaces_a_newer_one(self) -> None:
        """Computed at t2, then a late run for t1: the t2 rows stay."""
        offer = self.offers["B"]
        later = timezone.now()
        earlier = later - timedelta(minutes=5)

        ProjectionService().refresh([offer.pk], now=later)
        ProjectionService().refresh([offer.pk], now=earlier)

        rows = OfferScenarioProjection.objects.filter(offer=offer)
        assert rows
        assert all(row.computed_at == later for row in rows)

    def test_a_refresh_waits_for_another_holding_the_offer(self) -> None:
        """A second refresh of the same offer starts only after the first commits."""
        offer = self.offers["B"]
        locked, release, finished = (threading.Event() for _ in range(3))

        def hold() -> None:
            try:
                with transaction.atomic():
                    list(Offer.objects.select_for_update().filter(pk=offer.pk))
                    locked.set()
                    release.wait(timeout=10)
            finally:
                connections.close_all()

        def refresh() -> None:
            try:
                ProjectionService().refresh([offer.pk])
                finished.set()
            finally:
                connections.close_all()

        holder = threading.Thread(target=hold)
        holder.start()
        assert locked.wait(timeout=10)
        refresher = threading.Thread(target=refresh)
        refresher.start()

        blocked = not finished.wait(timeout=WAIT_SECONDS)
        release.set()
        holder.join(timeout=10)
        refresher.join(timeout=10)

        assert blocked
        assert finished.is_set()
