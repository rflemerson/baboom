"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

import json
from decimal import Decimal
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
    ProductNutrition,
    ProductStore,
    Store,
)
from core.tests.helpers import (
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
    EXPECTED_INLINE_COUNT = 2

    def setUp(self) -> None:
        """Create an operator and the references a product write needs."""
        self.user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.store = Store.objects.create(
            name="growth",
            display_name="Growth",
            scraper_slug="growth",
        )
        self.facts = NutritionFacts.objects.create(
            description="Natural",
            serving_size=Decimal(30),
            proteins=Decimal(24),
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


class AdminApiStoreLinkTests(TestCase):
    """Curation links a captured offer through the generic admin API.

    This is the exact surface an MCP client uses: no field is typed about the
    offer, the store comes from it, and a link that would price the wrong label
    is refused with a reason the client can act on.
    """

    URL = "/admin-api/api/v1/core/productstore/"

    def setUp(self) -> None:
        """Create a Natural whey and the Growth offers the scraper captured."""
        self.user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.store = Store.objects.create(
            name="Growth",
            display_name="Growth Supplements",
            scraper_slug="growth",
        )
        self.product = Product.objects.create(
            name="Whey Concentrado 1kg",
            brand=Brand.objects.create(name="growth", display_name="Growth"),
            net_mass=Decimal(1000),
        )
        self.natural = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(24),
            ),
        )
        self.natural.flavors.add(Flavor.objects.create(name="Natural"))
        self.offers = {
            flavor: Offer.objects.create(
                store_slug="growth",
                external_id=f"185:{flavor}",
                url=f"https://growth.example/whey?sabor={flavor}",
                current_price=Decimal("194.33"),
                options=[{"name": "Sabor", "value": flavor}],
            )
            for flavor in ("Natural", "Chocolate")
        }

    def _post(self, flavor: str) -> tuple[int, dict]:
        """Link the offer of one flavor to the Natural label."""
        response = self.client.post(
            self.URL,
            data=json.dumps(
                {
                    "product": self.product.pk,
                    "nutrition_profile": self.natural.pk,
                    "offer": self.offers[flavor].pk,
                },
            ),
            content_type="application/json",
        )
        return response.status_code, json.loads(response.content or b"{}")

    def test_a_captured_offer_is_linked_without_retyping_it(self) -> None:
        """The link reuses the offer and its history, and resolves the store."""
        status, body = self._post("Natural")

        assert status < HTTPStatus.BAD_REQUEST, body
        link = ProductStore.objects.get(product=self.product)
        assert link.offer == self.offers["Natural"]
        assert link.store == self.store
        assert Offer.objects.count() == len(self.offers)

    def test_a_link_to_the_wrong_label_is_refused_with_a_reason(self) -> None:
        """Chocolate cannot price the Natural label, and the client is told why."""
        status, body = self._post("Chocolate")

        assert status == HTTPStatus.BAD_REQUEST, body
        assert "Chocolate" in json.dumps(body)
        assert not ProductStore.objects.exists()

    def test_the_store_is_not_something_the_client_can_type(self) -> None:
        """The form spec offers the offer and the label, never the store."""
        response = self.client.get(f"{self.URL}add/form-spec/")
        fields = json.loads(response.content)["fields"]

        assert {"product", "nutrition_profile", "offer"} <= set(fields)
        assert "store" not in fields or fields["store"]["readonly"]


class ProductAdminActionTests(TestCase):
    """Coverage for manager-facing product deletion workflow."""

    def setUp(self) -> None:
        """Create a product with related store data."""
        self.factory = RequestFactory()
        self.admin = ProductAdmin(Product, django_admin.site)
        self.admin.message_user = Mock()
        self.brand = Brand.objects.create(name="dark-lab", display_name="Dark Lab")
        self.store = Store.objects.create(
            name="dark-lab",
            display_name="Dark Lab",
            scraper_slug="dark_lab",
        )
        self.product = Product.objects.create(
            name="Whey One Refil 900g - Dark Lab",
            brand=self.brand,
            net_mass=Decimal(900),
            packaging=Product.Packaging.REFILL,
        )
        profile = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(21),
            ),
        )
        self.store_link = _link_offer(
            product=self.product,
            nutrition_profile=profile,
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


class AdminApiLabelUnitTests(TestCase):
    """The admin API reads and writes masses in the unit the label prints.

    An agent sees only the form spec and the stored value; if either differs
    from the number on the package, the agent has to guess the conversion.
    """

    API = "/admin-api/api/v1/core"

    def setUp(self) -> None:
        """Create an operator and a brand to attach products to."""
        self.user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="growth", display_name="Growth")

    def _create_product(self) -> Product:
        """Create a 900 g product through the API, as a curator would."""
        response = self.client.post(
            f"{self.API}/product/",
            data=json.dumps(
                {
                    "name": "Whey 900g",
                    "kind": Product.Kind.SIMPLE,
                    "brand": self.brand.pk,
                    "net_mass": 900,
                    "packaging": Product.Packaging.OTHER,
                    "is_published": False,
                },
            ),
            content_type="application/json",
        )
        assert response.status_code < HTTPStatus.BAD_REQUEST, response.content
        return Product.objects.get(name="Whey 900g")

    def _patch(self, product: Product, payload: dict[str, object]) -> None:
        """PATCH a product through the API and require success."""
        response = self.client.patch(
            f"{self.API}/product/{product.pk}/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code < HTTPStatus.BAD_REQUEST, response.content

    def _form_spec(self, model_name: str) -> dict[str, dict[str, object]]:
        """Return the add form spec fields of a core model."""
        response = self.client.get(f"{self.API}/{model_name}/add/form-spec/")
        assert response.status_code == HTTPStatus.OK, response.content
        return json.loads(response.content)["fields"]

    def test_the_mass_typed_is_the_mass_stored(self) -> None:
        """900 typed for a 900 g package is 900 in the database."""
        assert self._create_product().net_mass == Decimal(900)

    def test_patching_another_field_leaves_the_mass_alone(self) -> None:
        """Repeated edits of unrelated fields must never rescale the mass."""
        product = self._create_product()

        self._patch(product, {"description": "first edit"})
        self._patch(product, {"description": "second edit"})

        product.refresh_from_db()
        assert product.net_mass == Decimal(900)
        assert product.is_published is False

    def test_form_spec_names_the_unit_of_every_mass(self) -> None:
        """Each mass field says which unit to type, and none claims another."""
        product = self._form_spec("product")
        facts = self._form_spec("nutritionfacts")
        expected = (
            (product, "net_mass", "(g)"),
            (facts, "serving_size", "(g)"),
            (facts, "proteins", "(g)"),
            (facts, "sodium", "(mg)"),
            (facts, "energy", "(kcal)"),
        )

        for fields, name, unit in expected:
            assert unit in str(fields[name]["label"]), (name, fields[name])
            assert "canonical" not in str(fields[name]["help_text"]), name


class NutritionFactsUsageTests(TestCase):
    """A shared table says who shares it before anyone edits it."""

    def test_retrieving_a_table_lists_every_label_that_prints_it(self) -> None:
        """Editing one table rewrites every product and flavor listed here."""
        user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        brand = Brand.objects.create(name="black-skull", display_name="Black Skull")
        facts = NutritionFacts.objects.create(
            serving_size=Decimal(30),
            proteins=Decimal(12),
        )
        for flavor in ("Chocolate", "Baunilha"):
            product = Product.objects.create(
                name=f"Whey 3W {flavor}",
                brand=brand,
                net_mass=Decimal(900),
            )
            profile = ProductNutrition.objects.create(
                product=product,
                nutrition_facts=facts,
            )
            profile.flavors.add(Flavor.objects.create(name=flavor))

        response = self.client.get(
            f"/admin-api/api/v1/core/nutritionfacts/{facts.pk}/",
        )

        body = json.dumps(json.loads(response.content), ensure_ascii=False)
        assert "Whey 3W Chocolate — Chocolate" in body
        assert "Whey 3W Baunilha — Baunilha" in body


class StoreLinkOfferChoiceTests(TestCase):
    """Picking an offer for a link only offers what can still be linked."""

    def test_the_offer_autocomplete_leaves_out_delisted_offers(self) -> None:
        """A delisted offer would only be refused after being chosen."""
        user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        Offer.objects.create(store_slug="growth", external_id="185-4", name="Whey live")
        gone = Offer.objects.create(
            store_slug="growth", external_id="185", name="Whey gone"
        )
        gone.delisted_at = gone.created_at
        gone.save(update_fields=["delisted_at"])

        response = self.client.get(
            "/admin/autocomplete/",
            {
                "app_label": "core",
                "model_name": "productstore",
                "field_name": "offer",
                "term": "whey",
            },
        )

        labels = [row["text"] for row in json.loads(response.content)["results"]]
        assert any("Whey live" in label for label in labels), labels
        assert not any("Whey gone" in label for label in labels), labels
