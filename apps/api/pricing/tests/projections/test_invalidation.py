"""Every dependency of a projection reprices exactly what it can reach."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.models import Brand, Product
from pricing.models import OfferScenarioProjection, PricingPolicyRevision, ShippingQuote
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import TwoProductCatalog
from promotions.models import PurchaseRoute

DELAY = "pricing.receivers.refresh_projections.delay"


class InvalidationTests(TwoProductCatalog, TestCase):
    """Routes, costs, policies, links and catalog scopes."""

    def setUp(self) -> None:
        """Project both offers."""
        super().setUp()
        ProjectionService().refresh()

    def _scheduled(self, change: object) -> list[object]:
        with patch(DELAY) as delay, self.captureOnCommitCallbacks(execute=True):
            change()
        return [call.kwargs.get("offer_ids") for call in delay.call_args_list]

    def test_a_route_expires_and_reprices_only_its_offer(self) -> None:
        """B's old link stops serving at once; A is untouched."""
        calls = self._scheduled(
            lambda: PurchaseRoute.objects.create(
                offer=self.offers["B"],
                kind="marketplace_listing",
                url="https://synthetic.example/b",
                fixes_seller=True,
            ),
        )
        now = timezone.now()

        b = OfferScenarioProjection.objects.filter(offer=self.offers["B"])
        a = OfferScenarioProjection.objects.filter(offer=self.offers["A"])
        assert calls == [[self.offers["B"].pk]]
        assert all(row.expires_at <= now for row in b)
        assert all(row.expires_at is None or row.expires_at > now for row in a)

    def test_a_shipping_quote_reprices_its_sellers_offers(self) -> None:
        """Both offers belong to the store's seller."""
        calls = self._scheduled(
            lambda: ShippingQuote.objects.create(
                group_fingerprint="g",
                seller_account=self.seller,
                country="BR",
                postal_code_hash="",
                amount=Decimal(10),
                currency_id="BRL",
                source="synthetic",
                expires_at=timezone.now() + timedelta(hours=1),
            ),
        )

        assert calls == [sorted(offer.pk for offer in self.offers.values())]

    def test_a_published_policy_reprices_everything(self) -> None:
        """A new public scenario needs every projection."""
        calls = self._scheduled(
            lambda: PricingPolicyRevision.objects.create(
                key="new",
                number=1,
                scenario="cash",
                published_at=timezone.now(),
            ),
        )

        assert calls == [None]

    def test_a_brand_change_reprices_the_products_offers(self) -> None:
        """A promotion scoped by brand may now reach product A."""
        product = Product.objects.get(name="A")

        def rebrand() -> None:
            product.brand = Brand.objects.create(name="other", display_name="Other")
            product.save()

        assert self._scheduled(rebrand) == [[self.offers["A"].pk]]
