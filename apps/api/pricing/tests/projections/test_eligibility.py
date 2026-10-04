"""SYNTHETIC: a change that takes a promotion away expires what it gave at once."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from commerce.models import Program
from core.models import Brand, Category, Product, ProductStore
from offers.models import Evidence
from pricing.models import OfferScenarioProjection
from pricing.projections import ProjectionService
from pricing.tests.projections.test_invalidation import DELAY
from pricing.tests.projections.test_projections import TwoProductCatalog
from promotions.models import (
    Promotion,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
    PurchaseRoute,
)
from promotions.services import PromotionService


class EligibilityCatalog(TwoProductCatalog):
    """A (R$ 100) and B (R$ 120), and a way to promote by any scope."""

    def setUp(self) -> None:
        """Project both offers."""
        super().setUp()
        ProjectionService().refresh()

    def _promote(self, kind: str, ref_id: int, rate: str = "30") -> None:
        """Publish an automatic discount on a scope of the catalog."""
        promotion = Promotion.objects.create(
            title=f"{kind} {ref_id}",
            issuer_seller=self.seller,
            source_key=f"{kind}-{ref_id}",
        )
        revision = PromotionRevision.objects.create(
            promotion=promotion,
            number=1,
            currency_id="BRL",
            timezone="America/Sao_Paulo",
            verified_at=timezone.now(),
        )
        PromotionScope.objects.create(
            revision=revision, role="target", kind=kind, ref_id=ref_id
        )
        PromotionEffect.objects.create(
            revision=revision,
            position=1,
            kind="percentage",
            stage="catalog",
            basis="current",
            target="item",
            allocation="per_line",
            parameters={"rate": rate},
        )
        revision.evidence.add(Evidence.objects.create(kind="announcement", excerpt="x"))
        with patch(DELAY):
            assert PromotionService().publish(revision, "executable").published
        ProjectionService().refresh()

    def _scheduled(self, change: object) -> list[object]:
        with (
            patch(DELAY) as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            change()
        return [call.kwargs.get("offer_ids") for call in delay.call_args_list]

    def _expired(self, name: str, *, key: str = "best") -> bool:
        row = OfferScenarioProjection.objects.get(
            offer=self.offers[name], policy__key=key, alternative="best"
        )
        return row.expires_at is not None and row.expires_at <= timezone.now()


class ProgrammeRouteTests(EligibilityCatalog, TestCase):
    """Add, remove and clear expire the route's offer, from either side."""

    def setUp(self) -> None:
        """Create a route to B and a programme."""
        super().setUp()
        self.route = PurchaseRoute.objects.create(
            offer=self.offers["B"],
            kind="marketplace_listing",
            url="https://synthetic.example/b",
        )
        self.program = Program.objects.create(
            name="Synthetic cashback", kind="cashback", issuer_seller=self.seller
        )
        ProjectionService().refresh()

    def _each_side(self) -> list[tuple[str, object, object]]:
        return [
            ("from the programme", self.program.compatible_routes, self.route),
            ("from the route", self.route.compatible_programs, self.program),
        ]

    def test_add_remove_and_clear_expire_the_offer_from_both_sides(self) -> None:
        """Every operation on either side reaches B and leaves A alone."""
        for side, related, other in self._each_side():
            operations = (
                ("add", lambda r=related, o=other: r.add(o), False),
                ("remove", lambda r=related, o=other: r.remove(o), True),
                ("clear", lambda r=related: r.clear(), True),
            )
            for name, operation, linked in operations:
                with self.subTest(side=side, operation=name):
                    if linked:
                        related.add(other)
                    ProjectionService().refresh()

                    calls = self._scheduled(operation)

                    assert self._expired("B")
                    assert not self._expired("A")
                    assert calls == [[self.offers["B"].pk]]
                    related.clear()


class LostEligibilityTests(EligibilityCatalog, TestCase):
    """Moving an offer, a product or a category can end a promotion's reach."""

    def test_moving_an_offer_to_another_product_expires_its_promotion(self) -> None:
        """A 30% discount on B's product: B's offer moves to A's product."""
        self._promote("product", Product.objects.get(name="B").pk)
        assert not self._expired("B")
        link = ProductStore.objects.get(offer=self.offers["B"])

        def move() -> None:
            link.product = Product.objects.get(name="A")
            link.save()

        calls = self._scheduled(move)

        assert self._expired("B")
        assert not self._expired("A")
        assert calls == [[self.offers["B"].pk]]

    def test_a_new_brand_expires_a_brand_promotion(self) -> None:
        """A discount on brand b: B changes brand, A keeps it."""
        brand = Product.objects.get(name="B").brand
        self._promote("brand", brand.pk)
        product = Product.objects.get(name="B")

        def rebrand() -> None:
            product.brand = Brand.objects.create(name="other", display_name="Other")
            product.save()

        self._scheduled(rebrand)

        assert self._expired("B")
        assert not self._expired("A")

    def test_a_product_save_that_keeps_brand_and_category_expires_nothing(
        self,
    ) -> None:
        """Renaming a product does not take a promotion away."""
        self._promote("brand", Product.objects.get(name="B").brand.pk)
        product = Product.objects.get(name="B")

        def rename() -> None:
            product.name = "B renamed"
            product.save()

        self._scheduled(rename)

        assert not self._expired("B")

    def test_moving_a_category_expires_what_its_old_ancestor_gave(self) -> None:
        """Product A under category C, under P1 (30% off); C moves under P2."""
        first = Category.add_root(name="P1")
        second = Category.add_root(name="P2")
        child = first.add_child(name="C")
        Product.objects.filter(name="A").update(category=child)
        self._promote("category", first.pk)
        assert not self._expired("A")
        assert OfferScenarioProjection.objects.get(
            offer=self.offers["A"], policy__key="best", alternative="best"
        ).explanation["applied"]

        calls = self._scheduled(
            lambda: Category.objects.move(
                Category.objects.get(pk=child.pk), second, "sorted-child"
            ),
        )

        assert self._expired("A")
        assert not self._expired("B")
        assert calls == [[self.offers["A"].pk]]
