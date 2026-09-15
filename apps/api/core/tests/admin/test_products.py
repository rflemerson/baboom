"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import Mock

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django_admin_rest_api.api.inlines import inline_name

from core.admin import ProductAdmin
from core.models import (
    Brand,
    Flavor,
    NutritionFacts,
    Product,
    ProductStore,
    Store,
)
from core.tests.helpers import (
    _grams,
    _link_offer,
)
from offers.models import Offer, PriceObservation


class AdminApiInlineWriteTests(TestCase):
    """Coverage for writing nutrition and store rows through the admin API.

    These exercise the generic ``inlines`` block of ``django-admin-rest-api``
    rather than a Baboom-specific endpoint: if the generic mechanism carries a
    product and its nutrition profile in one atomic request, the catalog needs
    no bespoke write path. Each test asserts the behaviour the curation flow
    requires, so a failure is a reproducible report against the library.
    """

    CREATE_URL = "/admin-api/api/v1/core/product/"
    # An inline is addressed by its formset prefix, which is the related
    # accessor and so is unique per relation.
    NUTRITION_INLINE = "nutrition_profiles"
    STORE_INLINE = "store_links"
    EXPECTED_INLINE_COUNT = 3

    def setUp(self) -> None:
        """Create an operator and the references a product write needs."""
        self.user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.store = Store.objects.create(name="growth", display_name="Growth")
        self.facts = NutritionFacts.objects.create(
            description="Natural",
            serving_size=_grams(30),
            proteins=_grams(24),
        )
        self.flavor = Flavor.objects.create(name="Natural")

    def _payload(self, **extra: object) -> dict[str, object]:
        """Return a minimal valid product payload, merged with the extras."""
        return {
            "name": "Whey Concentrado 900g",
            "kind": Product.Kind.SIMPLE,
            "brand": self.brand.pk,
            "net_mass": 900,
            "packaging": Product.Packaging.OTHER,
            "is_published": False,
            **extra,
        }

    def _post(self, payload: dict[str, object]) -> tuple[int, dict]:
        """POST a product payload and return the status and decoded body."""
        response = self.client.post(
            self.CREATE_URL,
            data=json.dumps(payload),
            content_type="application/json",
        )
        try:
            body = json.loads(response.content or b"{}")
        except json.JSONDecodeError:
            body = {}
        return response.status_code, body

    def test_product_and_nutrition_profile_are_created_together(self) -> None:
        """One request must land the product and its nutrition profile."""
        status, body = self._post(
            self._payload(
                inlines={
                    self.NUTRITION_INLINE: {
                        "items": [
                            {"pk": None, "fields": {"nutrition_facts": self.facts.pk}}
                        ],
                    },
                },
            ),
        )

        assert status < HTTPStatus.BAD_REQUEST, body
        product = Product.objects.get(name="Whey Concentrado 900g")
        assert product.nutrition_profiles.count() == 1
        assert product.nutrition_profiles.get().nutrition_facts_id == self.facts.pk

    def test_a_failing_inline_rolls_the_product_back(self) -> None:
        """A rejected row must leave no product behind, not a bare one.

        A product without a nutrition profile ranks nowhere, so a partial
        write is worse than no write.
        """
        status, body = self._post(
            self._payload(
                inlines={
                    self.NUTRITION_INLINE: {
                        "items": [{"pk": None, "fields": {"nutrition_facts": 999999}}],
                    },
                },
            ),
        )

        assert status == HTTPStatus.BAD_REQUEST, body
        assert not Product.objects.filter(name="Whey Concentrado 900g").exists()

    def test_nutrition_profile_accepts_its_flavors(self) -> None:
        """Flavors are many-to-many, and a profile without them is incomplete.

        Two flavors printing the same label share one profile, so the flavor
        list is what ties a profile to what it describes.
        """
        status, body = self._post(
            self._payload(
                inlines={
                    self.NUTRITION_INLINE: {
                        "items": [
                            {
                                "pk": None,
                                "fields": {
                                    "nutrition_facts": self.facts.pk,
                                    "flavors": [self.flavor.pk],
                                },
                            },
                        ],
                    },
                },
            ),
        )

        assert status < HTTPStatus.BAD_REQUEST, body
        profile = Product.objects.get(
            name="Whey Concentrado 900g"
        ).nutrition_profiles.get()
        assert list(profile.flavors.values_list("pk", flat=True)) == [self.flavor.pk]

    def test_every_declared_inline_is_addressable_by_a_distinct_name(self) -> None:
        """Two inlines sharing a name make one of them unreachable.

        ProductStore and ProductNutrition both call their parent link
        ``product``, so a name derived from the foreign key collides and the
        later inline shadows the earlier one.
        """
        request = RequestFactory().get(self.CREATE_URL)
        request.user = self.user
        model_admin = django_admin.site.get_model_admin(Product)
        # Resolved against a real parent, the way a write does it: without one
        # the foreign key is ambiguous and the fallback hides a collision
        # behind the child model name.
        parent = Product.objects.create(name="Reference", brand=self.brand)
        inlines = model_admin.get_inline_instances(request, parent)
        names = [inline_name(inline, parent, request) for inline in inlines]

        assert len(inlines) == self.EXPECTED_INLINE_COUNT
        assert len(set(names)) == len(names), f"colliding inline names: {names}"

    def test_store_listing_and_nutrition_travel_in_one_request(self) -> None:
        """Curation sets the offer link and the nutrition in the same write."""
        status, body = self._post(
            self._payload(
                inlines={
                    self.NUTRITION_INLINE: {
                        "items": [
                            {"pk": None, "fields": {"nutrition_facts": self.facts.pk}}
                        ],
                    },
                    self.STORE_INLINE: {
                        "items": [
                            {
                                "pk": None,
                                "fields": {
                                    "store": self.store.pk,
                                    "external_id": "growth-900",
                                    "product_link": "https://example.com/whey",
                                    "price": "129.90",
                                },
                            },
                        ],
                    },
                },
            ),
        )

        assert status < HTTPStatus.BAD_REQUEST, body
        product = Product.objects.get(name="Whey Concentrado 900g")
        assert product.nutrition_profiles.count() == 1
        assert product.store_links.count() == 1


class ProductAdminActionTests(TestCase):
    """Coverage for manager-facing product deletion workflow."""

    def setUp(self) -> None:
        """Create a product with related store data."""
        self.factory = RequestFactory()
        self.admin = ProductAdmin(Product, django_admin.site)
        self.admin.message_user = Mock()
        self.brand = Brand.objects.create(name="dark-lab", display_name="Dark Lab")
        self.store = Store.objects.create(name="dark-lab", display_name="Dark Lab")
        self.product = Product.objects.create(
            name="Whey One Refil 900g - Dark Lab",
            brand=self.brand,
            net_mass=_grams(900),
            packaging=Product.Packaging.REFILL,
        )
        self.store_link = _link_offer(
            product=self.product,
            store=self.store,
            external_id="568",
            product_link="https://example.com/whey",
            price=72.90,
        )
        self.offer = self.store_link.offer

    def test_delete_products_with_related_data_removes_related_records(self) -> None:
        """Admin action should remove store links while keeping offer observations."""
        request = self.factory.post("/admin/core/product/")

        self.admin.delete_products_with_related_data(
            request,
            Product.objects.filter(id=self.product.id),
        )

        assert Product.objects.filter(id=self.product.id).count() == 0
        assert ProductStore.objects.filter(id=self.store_link.id).count() == 0
        # Offers and their observations outlive the catalog product.
        assert Offer.objects.filter(id=self.offer.id).count() == 1
        assert PriceObservation.objects.filter(offer=self.offer).count() == 1
        self.admin.message_user.assert_called_once()
