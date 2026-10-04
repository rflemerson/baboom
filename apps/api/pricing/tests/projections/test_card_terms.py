"""SYNTHETIC: the REST product carries what the buyer needs to take the price."""

from __future__ import annotations

import json
from decimal import Decimal

from django.test import TestCase

from pricing.projections import ProjectionService
from pricing.tests.projections.test_benefit_alternatives import BenefitCatalog
from promotions.models import PurchaseRoute

URL = "/api/catalog/products/"


class CardTermsTests(BenefitCatalog, TestCase):
    """Coupon, payment, cashback and route reach the public product."""

    def _item(self, name: str, **params: str) -> dict:
        query = {"scenario": "best", "per_page": "12", **params}
        items = json.loads(self.client.get(URL, query).content)["items"]
        return next(item for item in items if item["name"] == name)

    def test_a_coupon_price_names_the_code(self) -> None:
        """B at R$ 120 with a R$ 20 coupon: R$ 100, and the code to use."""
        self._publish(
            self.offers["B"], "fixed_amount", {"amount": "20"}, code="SYNTH20"
        )
        ProjectionService().refresh()

        item = self._item("B")

        assert Decimal(item["price"]) == Decimal(100)
        assert item["couponCodes"] == ["SYNTH20"]
        assert item["cashback"] is None
        assert item["routeInstructions"] is None

    def test_cashback_is_shown_apart_and_never_taken_off_the_price(self) -> None:
        """A at R$ 100 with R$ 15 back: the price stays R$ 100."""
        self._publish(self.offers["A"], "cashback", {}, reward_rate=Decimal(15))
        ProjectionService().refresh()

        item = self._item("A")

        assert Decimal(item["price"]) == Decimal(100)
        assert item["cashback"] == {"amount": "15.00", "currency": "BRL"}
        assert item["couponCodes"] == []

    def test_the_route_instruction_travels_with_the_price(self) -> None:
        """A curated route with an instruction shows it."""
        PurchaseRoute.objects.create(
            offer=self.offers["A"],
            kind="direct",
            url="https://store.example/a?ref=synthetic",
            fixes_seller=True,
            instructions="Open the link before adding to the cart.",
        )
        ProjectionService().refresh()

        item = self._item("A")

        assert item["routeInstructions"] == "Open the link before adding to the cart."
        assert item["externalLink"] == "https://store.example/a?ref=synthetic"

    def test_a_plain_price_has_no_terms(self) -> None:
        """Nothing to execute: no code, cashback or instruction."""
        ProjectionService().refresh()

        item = self._item("A")

        assert item["couponCodes"] == []
        assert item["cashback"] is None
        assert item["routeInstructions"] is None
