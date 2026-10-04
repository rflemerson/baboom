"""Every dependency of a projection reprices exactly what it can reach."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin import site
from django.db import transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from commerce.models import Program
from core.models import Brand, Product, ProductStore
from offers.models import Offer, StockStatus
from pricing.admin import PricingPolicyRevisionAdmin
from pricing.models import OfferScenarioProjection, PricingPolicyRevision
from pricing.projections import ProjectionService
from pricing.tests.projections.test_projections import TwoProductCatalog
from promotions.models import PurchaseRoute
from promotions.services import PromotionService

DELAY = "pricing.invalidation.refresh_projections.delay"


class InvalidationTests(TwoProductCatalog, TestCase):
    """Routes, costs, policies, links and catalog scopes."""

    def setUp(self) -> None:
        """Project both offers."""
        super().setUp()
        ProjectionService().refresh()

    def _scheduled(self, change: object) -> list[object]:
        with (
            patch(DELAY) as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
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
        """The admin publishes through the workflow, which projects it."""
        policy = PricingPolicyRevision.objects.create(
            key="new",
            number=1,
            scenario="cash",
            rules={"allow_codes": True},
        )
        admin = PricingPolicyRevisionAdmin(PricingPolicyRevision, site)
        request = RequestFactory().post("/")
        queryset = PricingPolicyRevision.objects.filter(pk=policy.pk)

        with patch.object(admin, "message_user"):
            calls = self._scheduled(lambda: admin.publish(request, queryset))

        policy.refresh_from_db()
        assert policy.published_at is not None
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


class PreviousStateTests(TwoProductCatalog, TestCase):
    """A change reprices what it reached before, not only what it reaches now."""

    def setUp(self) -> None:
        """Project both offers."""
        super().setUp()
        ProjectionService().refresh()

    def _scheduled(self, change: object) -> list[object]:
        with (
            patch(DELAY) as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            change()
        return [call.kwargs.get("offer_ids") for call in delay.call_args_list]

    def _expired(self, name: str) -> bool:
        now = timezone.now()
        rows = OfferScenarioProjection.objects.filter(offer=self.offers[name])
        return all(row.expires_at is not None and row.expires_at <= now for row in rows)

    def test_moving_a_route_expires_its_old_offer_too(self) -> None:
        """A route moved from A to B: A's old link stops serving as well."""
        route = PurchaseRoute.objects.create(
            offer=self.offers["A"],
            kind="marketplace_listing",
            url="https://synthetic.example/a",
            fixes_seller=True,
        )
        ProjectionService().refresh()

        def move() -> None:
            route.offer = self.offers["B"]
            route.save()

        calls = self._scheduled(move)

        assert self._expired("A")
        assert self._expired("B")
        assert calls == [sorted(offer.pk for offer in self.offers.values())]

    def test_suspending_a_promotion_expires_the_price_it_gave(self) -> None:
        """B's promoted price stops serving before the refresh runs."""
        revision = self._promote_b("30")
        ProjectionService().refresh()

        with patch(DELAY):
            PromotionService.set_status(revision, "suspended")

        now = timezone.now()
        rows = OfferScenarioProjection.objects.filter(alternative="best")
        promoted = rows.get(offer=self.offers["B"], policy__key="best")
        normal = rows.get(offer=self.offers["B"], policy__key="normal")
        assert promoted.expires_at <= now
        assert normal.expires_at is None or normal.expires_at > now
        assert not self._expired("A")

    def test_a_rolled_back_savepoint_schedules_nothing(self) -> None:
        """Work undone inside a savepoint never reaches the queue."""
        product = Product.objects.get(name="A")

        def attempt() -> None:
            with transaction.atomic():
                product.save()
                transaction.set_rollback(True)

        assert self._scheduled(attempt) == []

    def test_each_call_schedules_its_own_idempotent_refresh(self) -> None:
        """Two saves in one transaction queue two tasks; none is merged away."""

        def save_both() -> None:
            for product in Product.objects.filter(name__in=["A", "B"]):
                product.save()

        calls = self._scheduled(save_both)

        assert sorted(calls) == sorted([offer.pk] for offer in self.offers.values())

    def test_a_programme_change_seen_from_the_programme_expires_its_routes(
        self,
    ) -> None:
        """Adding a route to a programme, from the programme's side."""
        route = PurchaseRoute.objects.create(
            offer=self.offers["B"],
            kind="marketplace_listing",
            url="https://synthetic.example/b",
        )
        program = Program.objects.create(
            name="Synthetic cashback",
            kind="cashback",
            issuer_seller=self.seller,
        )
        ProjectionService().refresh()

        calls = self._scheduled(lambda: program.compatible_routes.add(route))

        assert self._expired("B")
        assert calls == [[self.offers["B"].pk]]

    def test_relinking_to_another_offer_drops_the_old_offers_projections(
        self,
    ) -> None:
        """A's link now names a new offer: A is no longer ranked."""
        link = ProductStore.objects.get(offer=self.offers["A"])
        other = Offer.objects.create(
            store_slug="store",
            external_id="A-new",
            current_price=Decimal(95),
            current_stock_status=StockStatus.AVAILABLE,
            seller_account=self.seller,
        )

        def relink() -> None:
            link.offer = other
            link.save()

        calls = self._scheduled(relink)

        assert not OfferScenarioProjection.objects.filter(offer=self.offers["A"])
        assert calls == [[other.pk]]
