"""SYNTHETIC: work grows with the data only where it must.

These tests count queries, not seconds: a refresh or a load of many offers
issues the same queries as one of a few, so cost is bounded by the data the
database returns, not by round trips per offer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.models import Product, ProductStore
from offers.models import Offer, StockStatus
from pricing import projections
from pricing.facts import FactLoader
from pricing.models import PricingPolicyRevision
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import TwoProductCatalog
from promotions.services import PromotionService

if TYPE_CHECKING:
    from pricing.domain.engine import Inputs

PROMOTIONS = 30


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
        policy = PricingPolicyRevision.objects.get(key="best", number=1)
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


class WorkTests(TwoProductCatalog, TestCase):
    """Each evaluation reads only what reaches its offer."""

    def test_an_offer_is_evaluated_only_with_the_promotions_reaching_it(
        self,
    ) -> None:
        """Thirty promotions on B: A's evaluations receive none of them."""
        for index in range(PROMOTIONS):
            self._promote_b(str(index + 1))
        seen: dict[int, int] = {}
        real = projections.evaluate

        def counting(inputs: Inputs) -> object:
            (offer,) = inputs.offers
            seen[offer.id] = max(seen.get(offer.id, 0), len(inputs.revisions))
            return real(inputs)

        with patch.object(projections, "evaluate", counting):
            ProjectionService().refresh()

        assert seen[self.offers["A"].pk] == 0
        assert seen[self.offers["B"].pk] == PROMOTIONS

    def test_old_revisions_never_leave_the_database(self) -> None:
        """A promotion revised five times loads as one revision."""
        revision = self._promote_b("10")
        for _number in range(5):
            draft = PromotionService().revise(revision.promotion)
            with patch("pricing.invalidation.refresh_projections.delay"):
                assert PromotionService().publish(draft, "executable").published
            revision = draft

        loaded = FactLoader.revisions()

        assert [rule.id for rule in loaded] == [revision.pk]
