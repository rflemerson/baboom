"""Every dependency of a projection reprices exactly what it can reach."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.admin import site
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.models import Brand, Product, ProductStore
from pricing.admin import PricingPolicyRevisionAdmin
from pricing.models import OfferScenarioProjection, PricingPolicyRevision
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import TwoProductCatalog
from promotions.models import PurchaseRoute

DELAY = "pricing.invalidation.refresh_projections.delay"


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

    def test_publishing_a_policy_in_the_admin_reprices_everything(self) -> None:
        """A new public scenario needs every projection."""
        policy = PricingPolicyRevision(
            key="new",
            number=1,
            scenario="cash",
            published_at=timezone.now(),
        )
        admin = PricingPolicyRevisionAdmin(PricingPolicyRevision, site)

        calls = self._scheduled(
            lambda: admin.save_model(
                RequestFactory().post("/"), policy, None, change=False
            ),
        )

        assert calls == [None]

    def test_a_promotion_reprices_only_the_offers_it_targets(self) -> None:
        """A discount on B leaves A's projections alone."""
        calls = self._scheduled(lambda: self._promote_b("10"))

        assert calls == [[self.offers["B"].pk]]

    def test_unlinking_an_offer_drops_its_projections(self) -> None:
        """Nothing ranks an offer no product sells."""
        ProductStore.objects.filter(offer=self.offers["A"]).delete()

        assert not OfferScenarioProjection.objects.filter(offer=self.offers["A"])
        assert OfferScenarioProjection.objects.filter(offer=self.offers["B"])

    def test_a_brand_change_reprices_the_products_offers(self) -> None:
        """A promotion scoped by brand may now reach product A."""
        product = Product.objects.get(name="A")

        def rebrand() -> None:
            product.brand = Brand.objects.create(name="other", display_name="Other")
            product.save()

        assert self._scheduled(rebrand) == [[self.offers["A"].pk]]
