"""SYNTHETIC: work grows with the data only where it must.

These tests count queries, not seconds: a refresh or a load of many offers
issues the same queries as one of a few, so cost is bounded by the data the
database returns, not by round trips per offer.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.models import Product, ProductStore
from offers.models import Offer, StockStatus
from pricing.models import PricingPolicyRevision
from pricing.projections import ProjectionService
from pricing.services import FactLoader
from pricing.tests.projections.test_projections import TwoProductCatalog


class ScaleTests(TwoProductCatalog, TestCase):
    """Queries do not grow with the number of offers."""

    def _add(self, count: int) -> list[int]:
        model = Product.objects.get(name="A")
        start = Offer.objects.filter(external_id__startswith="bulk-").count()
        ids = []
        for index in range(start, start + count):
            product = Product.objects.create(
                name=f"P{index}",
                brand=model.brand,
                category=model.category,
                is_published=True,
            )
            offer = Offer.objects.create(
                store_slug="store",
                external_id=f"bulk-{index}",
                current_price=Decimal(100 + index),
                current_stock_status=StockStatus.AVAILABLE,
                seller_account=self.seller,
            )
            ProductStore.objects.create(product=product, offer=offer)
            ids.append(offer.pk)
        return ids

    def _queries(self, action: object) -> int:
        with CaptureQueriesContext(connection) as captured:
            action()
        return len(captured.captured_queries)

    def test_loading_facts_issues_a_fixed_number_of_queries(self) -> None:
        """Ten offers and fifty offers cost the same round trips."""
        policy = PricingPolicyRevision.objects.get(key="listed", number=1)
        few = self._add(10)
        many = few + self._add(40)

        small = self._queries(lambda: FactLoader().load(few, policy))
        large = self._queries(lambda: FactLoader().load(many, policy))

        assert small == large

    def test_a_refresh_issues_a_fixed_number_of_queries(self) -> None:
        """Projecting fifty offers issues no query per offer."""
        few = self._add(5)
        many = few + self._add(45)

        small = self._queries(lambda: ProjectionService().refresh(few))
        large = self._queries(lambda: ProjectionService().refresh(many))

        assert small == large, (small, large)
