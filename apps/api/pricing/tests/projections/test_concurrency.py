"""SYNTHETIC, PostgreSQL only: concurrent refreshes never publish an older price."""

from __future__ import annotations

import threading
import time
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import patch

from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from commerce.models import Currency
from offers.models import Offer
from pricing.facts import FactLoader
from pricing.models import OfferScenarioProjection, PricingPolicyRevision
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import TwoProductCatalog
from promotions.services import PromotionService

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pricing.facts import Facts

WAIT_SECONDS = 1.0
DELAY = "pricing.invalidation.refresh_projections.delay"


class PausingLoader(FactLoader):
    """Read the facts of one policy, then wait while the test changes them."""

    def __init__(
        self,
        policy_key: str,
        read: threading.Event,
        proceed: threading.Event,
    ) -> None:
        """Pause after reading this policy's facts, until ``proceed`` is set."""
        super().__init__()
        self.policy_key = policy_key
        self.read = read
        self.proceed = proceed

    def load(
        self,
        offer_ids: Iterable[int],
        policy: PricingPolicyRevision,
    ) -> Facts:
        """Load the facts; for the chosen policy, hold the refresh afterwards."""
        facts = super().load(offer_ids, policy)
        if policy.key == self.policy_key:
            self.read.set()
            self.proceed.wait(timeout=10)
            time.sleep(WAIT_SECONDS)
        return facts


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

    def test_a_refresh_racing_an_invalidation_never_keeps_the_old_promotion(
        self,
    ) -> None:
        """A refresh that read the promotion before it was suspended.

        The refresh holds the offer while the promotion is suspended and
        invalidated in another transaction. When both are done the published
        price either reflects the suspension or is expired, waiting for the
        refresh task: never the old promotion as a valid price.
        """
        offer = self.offers["B"]
        PricingPolicyRevision.objects.create(
            key="racing",
            number=1,
            scenario="best",
            rules={"freshness_hours": 72},
            published_at=timezone.now(),
        )
        with patch(DELAY):
            revision = self._promote_b("30")
        ProjectionService().refresh([offer.pk])
        facts_read, suspending = threading.Event(), threading.Event()
        loader = PausingLoader("racing", facts_read, suspending)

        def refresh() -> None:
            try:
                ProjectionService(loader).refresh([offer.pk])
            finally:
                connections.close_all()

        def suspend() -> None:
            try:
                facts_read.wait(timeout=10)
                suspending.set()
                with patch(DELAY):
                    PromotionService.set_status(revision, "suspended")
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=refresh),
            threading.Thread(target=suspend),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        row = OfferScenarioProjection.objects.get(
            offer=offer, policy__key="racing", alternative="best"
        )
        valid = row.expires_at is None or row.expires_at > timezone.now()
        assert not (valid and row.amount == Decimal("84.00"))
