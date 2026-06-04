"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

import json
from decimal import Decimal
from http import HTTPStatus
from typing import Protocol, cast
from unittest.mock import Mock

from django.contrib import admin as django_admin
from django.core.exceptions import ValidationError
from django.forms.models import inlineformset_factory
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core.admin import ProductAdmin
from core.dtos import (
    CatalogProductsFilters,
    ComboComponentInput,
    NutritionFactsPayload,
    ProductCreateInput,
    ProductMetadataUpdateInput,
    ProductNutritionPayload,
    StoreListingPayload,
)
from core.forms import ProductStoreInlineForm, ProductStoreInlineFormSet
from core.models import (
    AlertSubscriber,
    Brand,
    Category,
    NutritionFacts,
    Product,
    ProductComponent,
    ProductNutrition,
    ProductStore,
    Store,
)
from core.selectors import public_catalog_products, public_catalog_products_with_stats
from core.services import (
    ComboResolutionService,
    ProductCreateService,
    ProductMetadataUpdateService,
    ProductNutritionService,
    ProductStoreService,
)
from offers.models import Offer, PriceObservation, StockStatus


def _link_offer(
    **kwargs: object,
) -> ProductStore:
    """Create an offer-backed store listing for tests.

    Mirrors the production model: the price series lives on the merchant offer,
    while ``ProductStore`` only links the product to that offer.
    """
    product = cast("Product", kwargs["product"])
    store = cast("Store", kwargs["store"])
    external_id = cast("str | None", kwargs.get("external_id"))
    product_link = cast("str", kwargs.get("product_link", ""))
    price = cast("float | Decimal | None", kwargs.get("price"))
    stock_status = cast("str", kwargs.get("stock_status", StockStatus.AVAILABLE))
    resolved_external_id = (
        external_id if external_id is not None else f"{store.name}-{product.pk}"
    )
    resolved_price = Decimal(str(price)) if price is not None else None
    offer = Offer.objects.create(
        store_slug=store.name,
        external_id=resolved_external_id,
        url=product_link,
        current_price=resolved_price,
        current_stock_status=stock_status,
    )
    if resolved_price is not None:
        PriceObservation.objects.create(
            offer=offer,
            price=resolved_price,
            stock_status=stock_status,
        )
    return ProductStore.objects.create(product=product, store=store, offer=offer)


class CatalogAnnotatedProduct(Protocol):
    """Typed surface for selector rows with catalog annotations."""

    concentration: Decimal | None
    total_protein: Decimal | None
    price_per_protein_gram: Decimal | None
    external_link: str | None
    last_price: Decimal | None


class ProductStoreServiceTests(TestCase):
    """Coverage for store listing synchronization rules."""

    UPDATED_HISTORY_COUNT = 2
    UPDATED_PRICE = Decimal("109.90")

    def setUp(self) -> None:
        """Create a product and two stores for listing sync tests."""
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Whey Concentrado",
            brand=self.brand,
            weight=900,
            packaging=Product.Packaging.CONTAINER,
        )
        self.store = Store.objects.create(name="growth", display_name="Growth")
        self.other_store = Store.objects.create(name="dux", display_name="Dux")
        self.service = ProductStoreService()

    def test_replace_listings_updates_existing_listing_without_recreating_it(
        self,
    ) -> None:
        """Existing listings should keep identity while mutable fields are updated."""
        original_listing = _link_offer(
            product=self.product,
            store=self.store,
            external_id="sku-1",
            product_link="https://growth.example/old",
            price=99.90,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_name="Growth",
                    external_id="sku-2",
                    product_link="https://growth.example/new",
                    affiliate_link="https://aff.example/new",
                    price=99.90,
                    stock_status=StockStatus.AVAILABLE,
                ),
            ],
        )

        updated_listing = ProductStore.objects.get(
            product=self.product,
            store=self.store,
        )
        assert updated_listing.pk == original_listing.pk
        assert updated_listing.external_id == "sku-2"
        assert updated_listing.product_link == "https://growth.example/new"
        assert updated_listing.affiliate_link == "https://aff.example/new"
        assert updated_listing.offer.price_observations.count() == 1

    def test_store_inline_requires_external_id_for_listing_rows(self) -> None:
        """Manual listings need a stable merchant id before creating an offer."""
        formset_class = inlineformset_factory(
            Product,
            ProductStore,
            form=ProductStoreInlineForm,
            formset=ProductStoreInlineFormSet,
            fields=(
                "store",
                "external_id",
                "product_link",
                "affiliate_link",
                "price",
                "stock_status",
            ),
            extra=1,
            can_delete=True,
        )
        formset = formset_class(
            data={
                "store_links-TOTAL_FORMS": "1",
                "store_links-INITIAL_FORMS": "0",
                "store_links-MIN_NUM_FORMS": "0",
                "store_links-MAX_NUM_FORMS": "1000",
                "store_links-0-store": str(self.store.id),
                "store_links-0-external_id": "",
                "store_links-0-product_link": "https://growth.example/item",
                "store_links-0-affiliate_link": "",
                "store_links-0-price": "99.90",
                "store_links-0-stock_status": StockStatus.AVAILABLE,
            },
            instance=self.product,
            prefix="store_links",
        )

        assert not formset.is_valid()
        assert "store product ID" in str(formset.non_form_errors())

    def test_replace_listings_adds_history_only_when_price_or_stock_changes(
        self,
    ) -> None:
        """A new price observation should be appended only for meaningful changes."""
        listing = _link_offer(
            product=self.product,
            store=self.store,
            external_id="sku-1",
            product_link="https://growth.example/item",
            price=99.90,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_name="Growth",
                    external_id="sku-1",
                    product_link="https://growth.example/item",
                    price=109.90,
                    stock_status=StockStatus.LAST_UNITS,
                ),
            ],
        )

        listing.refresh_from_db()
        observations = listing.offer.price_observations
        latest_history = observations.first()
        assert observations.count() == self.UPDATED_HISTORY_COUNT
        assert latest_history is not None
        assert latest_history.price == self.UPDATED_PRICE
        assert latest_history.stock_status == StockStatus.LAST_UNITS

    def test_replace_listings_deletes_removed_store_links(self) -> None:
        """Listings omitted from the desired state should be removed."""
        retained_listing = _link_offer(
            product=self.product,
            store=self.store,
            external_id="growth-1",
            product_link="https://growth.example/item",
            price=99.90,
        )
        removed_listing = _link_offer(
            product=self.product,
            store=self.other_store,
            external_id="dux-1",
            product_link="https://dux.example/item",
            price=89.90,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_name="Growth",
                    external_id="growth-1",
                    product_link="https://growth.example/item",
                    price=99.90,
                ),
            ],
        )

        assert ProductStore.objects.filter(pk=retained_listing.pk).exists()
        assert not ProductStore.objects.filter(pk=removed_listing.pk).exists()

    def test_replace_listings_rejects_duplicate_store_rows(self) -> None:
        """The same store should not be accepted twice for one product."""
        raised_validation_error = False

        try:
            self.service.replace_listings(
                self.product,
                [
                    StoreListingPayload(
                        store_name="Growth",
                        external_id="growth-1",
                        product_link="https://growth.example/1",
                        price=99.90,
                    ),
                    StoreListingPayload(
                        store_name="Growth",
                        external_id="growth-2",
                        product_link="https://growth.example/2",
                        price=109.90,
                    ),
                ],
            )
        except ValidationError:
            raised_validation_error = True

        assert raised_validation_error


class ProductCreateServiceTests(TestCase):
    """Essential coverage for product creation workflows."""

    EXPECTED_TAG_COUNT = 2
    EXPECTED_COMPONENT_COUNT = 2
    COMPONENT_WEIGHT = 300
    EXPECTED_DEDUPED_COMPONENT_QUANTITY = 3

    def setUp(self) -> None:
        """Create reusable fixtures and services."""
        self.service = ProductCreateService()
        self.store = Store.objects.create(name="growth", display_name="Growth")

    def test_execute_creates_simple_product_with_taxonomy_nutrition_and_store(
        self,
    ) -> None:
        """Simple product creation should persist related catalog data."""
        product = self.service.execute(
            ProductCreateInput(
                name="Whey Isolate",
                weight=900,
                brand_name="Growth",
                category_name=["Supplements", "Protein"],
                ean="1234567890123",
                description="Lean whey isolate",
                is_published=True,
                tags=[["Goal", "Muscle"], ["Type", "Whey"]],
                stores=[
                    StoreListingPayload(
                        store_name="Growth",
                        external_id="growth-900",
                        product_link="https://growth.example/whey",
                        price=149.90,
                    ),
                ],
                nutrition=[
                    ProductNutritionPayload(
                        nutrition_facts=NutritionFactsPayload(
                            description="Isolate profile",
                            serving_size_grams=30,
                            energy_kcal=120,
                            proteins=26,
                            carbohydrates=2,
                            total_fats=1,
                        ),
                    ),
                ],
            ),
        )

        product.refresh_from_db()
        assert product.type == Product.Type.SIMPLE
        assert product.brand.display_name == "Growth"
        assert product.category is not None
        assert product.category.name == "Protein"
        assert product.tags.count() == self.EXPECTED_TAG_COUNT
        assert product.store_links.count() == 1
        assert product.nutrition_profiles.count() == 1
        listing = product.store_links.first()
        assert listing is not None
        assert listing.offer.price_observations.count() == 1

    def test_execute_creates_combo_component_product_with_rich_payload_when_unmatched(
        self,
    ) -> None:
        """Combo creation should create component products with the submitted data."""
        product = self.service.execute(
            ProductCreateInput(
                name="Combo Pré + Creatina",
                weight=1300,
                brand_name="Growth",
                packaging=Product.Packaging.CONTAINER,
                is_combo=True,
                components=[
                    ComboComponentInput(
                        name="Pré-treino",
                        weight=self.COMPONENT_WEIGHT,
                        brand_name="Growth",
                        category_name=["Energy", "Pre-Workout"],
                        ean="7891000000001",
                        description="Pré-treino do combo",
                        packaging=Product.Packaging.CONTAINER,
                        stores=[
                            StoreListingPayload(
                                store_name="Growth",
                                external_id="pre-300",
                                product_link="https://growth.example/pre-300",
                                price=79.90,
                            ),
                        ],
                        quantity=1,
                    ),
                    ComboComponentInput(
                        name="Creatina",
                        weight=self.COMPONENT_WEIGHT,
                        category_name=["Energy", "Creatine"],
                        description="Creatina do combo",
                        packaging=Product.Packaging.REFILL,
                        quantity=1,
                    ),
                ],
            ),
        )
        assert product.type == Product.Type.COMBO
        component_links = list(
            ProductComponent.objects.filter(parent=product).select_related("component"),
        )
        assert len(component_links) == self.EXPECTED_COMPONENT_COUNT

        first_component = component_links[0].component
        second_component = component_links[1].component

        assert first_component.name == "Pré-treino"
        assert first_component.weight == self.COMPONENT_WEIGHT
        assert first_component.ean == "7891000000001"
        assert first_component.packaging == Product.Packaging.CONTAINER
        assert first_component.category is not None
        assert first_component.category.name == "Pre-Workout"
        assert first_component.store_links.count() == 1
        assert first_component.is_published is False

        assert second_component.name == "Creatina"
        assert second_component.weight == self.COMPONENT_WEIGHT
        assert second_component.packaging == Product.Packaging.REFILL
        assert second_component.is_published is False

    def test_execute_sums_duplicate_combo_component_quantities(self) -> None:
        """Duplicate component inputs should produce one link with summed quantity."""
        product = self.service.execute(
            ProductCreateInput(
                name="Combo Creatina",
                weight=600,
                brand_name="Growth",
                is_combo=True,
                components=[
                    ComboComponentInput(
                        name="Creatina",
                        weight=self.COMPONENT_WEIGHT,
                        brand_name="Growth",
                        ean="7891000000002",
                        quantity=1,
                    ),
                    ComboComponentInput(
                        name="Creatina",
                        weight=self.COMPONENT_WEIGHT,
                        brand_name="Growth",
                        ean="7891000000002",
                        quantity=2,
                    ),
                ],
            ),
        )

        link = product.component_links.get()
        assert link.quantity == self.EXPECTED_DEDUPED_COMPONENT_QUANTITY

    def test_combo_resolution_rejects_simple_parent(self) -> None:
        """Component links should only be managed for combo products."""
        brand = Brand.objects.create(name="simple-brand", display_name="Simple Brand")
        product = Product.objects.create(
            name="Simple Product",
            brand=brand,
            packaging=Product.Packaging.CONTAINER,
        )

        raised_validation_error = False
        try:
            ComboResolutionService().resolve_combo_components(
                product,
                [
                    ComboComponentInput(
                        name="Creatina",
                        brand_name="Growth",
                    ),
                ],
            )
        except ValidationError:
            raised_validation_error = True

        assert raised_validation_error

    def test_execute_rejects_duplicate_ean(self) -> None:
        """Product creation should reject duplicate EAN values."""
        Brand.objects.create(name="existing-brand", display_name="Existing Brand")
        Product.objects.create(
            name="Existing Whey",
            brand=Brand.objects.get(name="existing-brand"),
            weight=900,
            ean="1234567890123",
            packaging=Product.Packaging.CONTAINER,
        )

        raised_validation_error = False

        try:
            self.service.execute(
                ProductCreateInput(
                    name="Another Whey",
                    weight=900,
                    brand_name="Growth",
                    ean="1234567890123",
                ),
            )
        except ValidationError:
            raised_validation_error = True

        assert raised_validation_error


class ProductMetadataUpdateServiceTests(TestCase):
    """Essential coverage for product metadata updates."""

    EXPECTED_TAG_COUNT = 2

    def setUp(self) -> None:
        """Create a baseline product for metadata update tests."""
        self.service = ProductMetadataUpdateService()
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Old Whey",
            brand=self.brand,
            weight=900,
            packaging=Product.Packaging.CONTAINER,
            description="Old description",
        )

    def test_execute_updates_content_category_and_tags(
        self,
    ) -> None:
        """Metadata updates should apply resolved taxonomy."""
        updated_product = self.service.execute(
            product_id=self.product.id,
            data=ProductMetadataUpdateInput(
                name="New Whey",
                description="New description",
                packaging=Product.Packaging.REFILL,
                category_name=["Supplements", "Protein"],
                tags=[["Goal", "Muscle"], ["Type", "Whey"]],
            ),
        )

        updated_product.refresh_from_db()
        assert updated_product.name == "New Whey"
        assert updated_product.description == "New description"
        assert updated_product.packaging == Product.Packaging.REFILL
        assert updated_product.category is not None
        assert updated_product.category.name == "Protein"
        assert updated_product.tags.count() == self.EXPECTED_TAG_COUNT

    def test_execute_can_clear_category_when_empty_string_is_provided(self) -> None:
        """Empty-string category updates should remove the current category."""
        category = Category.add_root(name="Supplements")
        self.product.category = category
        self.product.save()

        updated_product = self.service.execute(
            product_id=self.product.id,
            data=ProductMetadataUpdateInput(category_name=""),
        )

        assert updated_product.category is None

    def test_execute_updates_published_state(self) -> None:
        """Published state should persist through the metadata update workflow."""
        assert self.product.is_published is False

        updated_product = self.service.execute(
            product_id=self.product.id,
            data=ProductMetadataUpdateInput(is_published=True),
        )

        updated_product.refresh_from_db()
        assert updated_product.is_published is True


class ProductNutritionServiceTests(TestCase):
    """Essential coverage for admin-facing nutrition selection workflow."""

    REPEATED_PAYLOAD_COUNT = 2

    def setUp(self) -> None:
        """Create a product and reusable nutrition facts."""
        self.service = ProductNutritionService()
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Whey",
            brand=self.brand,
            weight=900,
            packaging=Product.Packaging.CONTAINER,
        )
        self.existing_facts = NutritionFacts.objects.create(
            description="Existing table",
            serving_size_grams=30,
            energy_kcal=120,
            proteins=Decimal(24),
            carbohydrates=Decimal(3),
            total_fats=Decimal(2),
        )

    def test_attach_profiles_creates_new_facts_for_repeated_payloads(self) -> None:
        """Repeated payloads should not be deduplicated by nutrition content."""
        payload = ProductNutritionPayload(
            nutrition_facts=NutritionFactsPayload(
                description="Repeated table",
                serving_size_grams=30,
                energy_kcal=120,
                proteins=24,
                carbohydrates=3,
                total_fats=2,
            ),
        )

        self.service.attach_profiles(self.product, [payload])
        self.service.attach_profiles(self.product, [payload])

        assert (
            NutritionFacts.objects.filter(description="Repeated table").count()
            == self.REPEATED_PAYLOAD_COUNT
        )
        assert self.product.nutrition_profiles.count() == self.REPEATED_PAYLOAD_COUNT

    def test_attach_profiles_truncates_long_facts_description(self) -> None:
        """Nutrition facts descriptions should fit the model field."""
        long_description = "x" * 250
        payload = ProductNutritionPayload(
            nutrition_facts=NutritionFactsPayload(
                description=long_description,
                serving_size_grams=30,
                energy_kcal=120,
                proteins=24,
                carbohydrates=3,
                total_fats=2,
            ),
        )

        self.service.attach_profiles(self.product, [payload])

        facts = self.product.nutrition_profiles.get().nutrition_facts
        max_length = ProductNutritionService.MAX_FACTS_DESCRIPTION_LENGTH
        assert len(facts.description) == max_length
        assert facts.description == long_description[:max_length]

    def test_attach_profiles_normalizes_invalid_micronutrient_unit(self) -> None:
        """Micronutrient units from model output should fall back to unknown."""
        payload = ProductNutritionPayload(
            nutrition_facts=NutritionFactsPayload(
                description="Micronutrients",
                serving_size_grams=30,
                energy_kcal=120,
                proteins=24,
                carbohydrates=3,
                total_fats=2,
                micronutrients=[
                    {
                        "name": "Glicina",
                        "value": 360,
                        "unit": "mg,value:360},{name:",
                    },
                ],
            ),
        )

        self.service.attach_profiles(self.product, [payload])

        micronutrient = (
            self.product.nutrition_profiles.get().nutrition_facts.micronutrients.get()
        )
        assert micronutrient.unit == ProductNutritionService.DEFAULT_MICRONUTRIENT_UNIT


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
            weight=900,
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


class ProductStatsTest(TestCase):
    """Tests for the public catalog selector annotations."""

    def setUp(self) -> None:
        """Set up test data."""
        self.brand = Brand.objects.create(name="Test Brand", display_name="Test Brand")
        self.store = Store.objects.create(name="Test Store", display_name="Test Store")

        self.product = Product.objects.create(
            name="Whey Protein",
            brand=self.brand,
            weight=1000,
        )

        self.nutrition = NutritionFacts.objects.create(
            serving_size_grams=30,
            proteins=Decimal("24.0"),
            carbohydrates=0,
            total_fats=0,
            description="Standard Whey",
            energy_kcal=120,
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.nutrition,
        )

        self.link = _link_offer(
            product=self.product,
            store=self.store,
            product_link="https://example.com",
            price=100.00,
        )

    def test_protein_calculations(self) -> None:
        """Derived protein metrics should be correctly annotated."""
        product = cast(
            "CatalogAnnotatedProduct | None",
            public_catalog_products_with_stats().first(),
        )

        assert product is not None
        assert product.concentration == Decimal("80.0")
        assert product.total_protein == Decimal("800.00")
        assert round(product.price_per_protein_gram, 3) == Decimal("0.125")
        assert product.external_link == "https://example.com"

    def test_missing_price_handling(self) -> None:
        """Products without price should keep nullable metrics."""
        product_without_price = Product.objects.create(
            name="No Price Whey",
            brand=self.brand,
            weight=500,
        )

        result = cast(
            "CatalogAnnotatedProduct | None",
            public_catalog_products_with_stats()
            .filter(
                pk=product_without_price.pk,
            )
            .first(),
        )

        assert result is not None
        assert result.last_price is None
        assert result.price_per_protein_gram is None
        assert result.external_link is None

    def test_latest_price_and_external_link_use_same_history_row_on_timestamp_tie(
        self,
    ) -> None:
        """Latest price annotations should stay consistent under observed_at ties."""
        second_store = Store.objects.create(
            name="Second Store",
            display_name="Second Store",
        )
        second_link = _link_offer(
            product=self.product,
            store=second_store,
            product_link="https://example.com/second",
            price=150.00,
        )

        first_history = self.link.offer.price_observations.first()
        second_history = second_link.offer.price_observations.first()
        tied_timestamp = timezone.now()
        PriceObservation.objects.filter(
            id__in=[first_history.id, second_history.id],
        ).update(observed_at=tied_timestamp)

        product = cast(
            "CatalogAnnotatedProduct | None",
            public_catalog_products_with_stats().get(pk=self.product.pk),
        )

        assert product is not None
        assert product.last_price == Decimal("150.00")
        assert product.external_link == "https://example.com/second"

    def test_catalog_uses_most_protein_dense_nutrition_profile(self) -> None:
        """Catalog metrics should use the most protein-dense nutrition profile."""
        denser_profile = NutritionFacts.objects.create(
            serving_size_grams=30,
            proteins=Decimal("27.0"),
            carbohydrates=0,
            total_fats=0,
            description="Isolate profile",
            energy_kcal=120,
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=denser_profile,
        )

        product = cast(
            "CatalogAnnotatedProduct | None",
            public_catalog_products_with_stats().get(pk=self.product.pk),
        )

        assert product is not None
        assert product.concentration == Decimal("90.0")
        assert product.total_protein == Decimal("900.00")
        assert round(product.price_per_protein_gram, 3) == Decimal("0.111")

    def test_catalog_sorting_is_stable_when_metric_values_tie(self) -> None:
        """Sorting should use a stable fallback under metric ties."""
        alpha_brand = Brand.objects.create(name="Alpha", display_name="Alpha")
        beta_brand = Brand.objects.create(name="Beta", display_name="Beta")
        alpha = Product.objects.create(
            name="Whey A",
            brand=alpha_brand,
            weight=1000,
            is_published=True,
        )
        beta = Product.objects.create(
            name="Whey B",
            brand=beta_brand,
            weight=1000,
            is_published=True,
        )

        for product in (alpha, beta):
            ProductNutrition.objects.create(
                product=product,
                nutrition_facts=self.nutrition,
            )

        _link_offer(
            product=alpha,
            store=self.store,
            product_link="https://example.com/alpha",
            price=100.00,
        )
        _link_offer(
            product=beta,
            store=self.store,
            product_link="https://example.com/beta",
            price=100.00,
        )

        items = list(
            public_catalog_products(
                CatalogProductsFilters(sort_by="last_price", sort_dir="asc"),
            ).values_list("brand__name", "name"),
        )

        assert items[:2] == [("Alpha", "Whey A"), ("Beta", "Whey B")]


class PublicAlertSubscriptionRESTTests(TestCase):
    """Tests for the public alert subscription REST endpoint."""

    def _execute_subscription(
        self,
        email: str,
    ) -> dict[str, object]:
        """Execute the alert subscription REST endpoint and decode the JSON response."""
        response = self.client.post(
            "/api/alerts/subscribe/",
            data=json.dumps({"email": email}),
            content_type="application/json",
        )
        return json.loads(response.content)

    def test_subscribe_alerts_creates_new_subscriber(self) -> None:
        """A new public email subscription should succeed through REST."""
        result = self._execute_subscription("new-subscriber@example.com")

        assert result["success"]
        assert not result["alreadySubscribed"]
        assert result["email"] == "new-subscriber@example.com"

    def test_subscribe_alerts_returns_duplicate_state(self) -> None:
        """Duplicate subscriptions should be reported explicitly."""
        subscriber = AlertSubscriber.objects.create(email="duplicate@example.com")

        result = self._execute_subscription(subscriber.email)

        assert not result["success"]
        assert result["alreadySubscribed"]
        assert result["email"] == subscriber.email

    def test_subscribe_alerts_returns_validation_errors(self) -> None:
        """Invalid emails should return formatted validation errors."""
        result = self._execute_subscription("not-an-email")

        assert not result["success"]
        assert result["email"] == "not-an-email"
        assert result["errors"][0]["field"] == "email"


class PublicEndpointSecurityTests(TestCase):
    """Tests for public endpoint access rules."""

    def test_public_catalog_rest_query_without_api_key(self) -> None:
        """Public REST catalog requests should be allowed without API key."""
        response = self.client.get("/api/catalog/products/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert "public" in response["Cache-Control"]
        assert "s-maxage=21600" in response["Cache-Control"]
        assert payload["pageInfo"]["totalCount"] == 0

    def test_healthz_without_api_key(self) -> None:
        """Healthchecks should not depend on GraphQL authentication."""
        response = self.client.get("/healthz/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert payload == {"status": "ok"}

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz/$"])
    def test_healthz_skips_production_ssl_redirect(self) -> None:
        """Container healthchecks should receive a direct 200 in production."""
        response = self.client.get("/healthz/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert payload == {"status": "ok"}
