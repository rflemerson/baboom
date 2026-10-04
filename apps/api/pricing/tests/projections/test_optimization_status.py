"""SYNTHETIC: a bounded search is stored and shown, never passed as complete."""

from __future__ import annotations

import json

from django.test import TestCase, override_settings
from django.utils import timezone

from pricing.models import OfferScenarioProjection, PricingPolicyRevision
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import TwoProductCatalog

URL = "/api/catalog/products/"


class OptimizationStatusTests(TwoProductCatalog, TestCase):
    """The projection keeps the search's status and the REST product shows it."""

    def setUp(self) -> None:
        """Publish a policy whose budget cannot cover a promotion's search."""
        super().setUp()
        PricingPolicyRevision.objects.create(
            key="tight",
            number=1,
            scenario="best",
            rules={"max_combinations": 1, "freshness_hours": 72},
            published_at=timezone.now(),
        )
        self._promote_b("30")
        ProjectionService().refresh()

    def _items(self, **params: str) -> dict[str, dict]:
        query = {"scenario": "tight", "per_page": "12", **params}
        items = json.loads(self.client.get(URL, query).content)["items"]
        return {item["name"]: item for item in items}

    def test_the_projection_keeps_the_status_of_its_search(self) -> None:
        """B has a promotion the budget cannot search; A has nothing to search."""
        rows = OfferScenarioProjection.objects.filter(
            policy__key="tight", alternative="best"
        )

        assert rows.get(offer=self.offers["B"]).optimization_status == "bounded"
        assert rows.get(offer=self.offers["A"]).optimization_status == "complete"

    def test_the_rest_product_exposes_the_status(self) -> None:
        """The catalog says which prices came from a cut search."""
        items = self._items()

        assert items["B"]["optimizationStatus"] == "bounded"
        assert items["A"]["optimizationStatus"] == "complete"

    @override_settings(PRICING_PROJECTION_COUNTRIES=[])
    def test_a_price_read_from_the_last_crawl_states_no_search(self) -> None:
        """Without projections nothing was searched: the status is null."""
        items = self._items()

        assert items["A"]["optimizationStatus"] is None
