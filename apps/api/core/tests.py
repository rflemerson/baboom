"""Tests for core services, selectors, and GraphQL boundaries."""

from __future__ import annotations

import json
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING, Protocol, cast
from unittest.mock import Mock

from django.contrib import admin as django_admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from strawberry.django.views import GraphQLView

from baboom.schema import schema
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
from core.models import (
    AlertSubscriber,
    APIKey,
    Brand,
    Category,
    NutritionFacts,
    Product,
    ProductComponent,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
)
from core.selectors import public_catalog_products, public_catalog_products_with_stats
from core.services import (
    ProductCreateService,
    ProductMetadataUpdateService,
    ProductNutritionService,
    ProductStoreService,
)
from scrapers.models import ScrapedItem, ScrapedPage

if TYPE_CHECKING:
    from django.http import HttpResponse


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
        original_listing = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="sku-1",
            product_link="https://growth.example/old",
            affiliate_link="https://aff.example/old",
        )
        ProductPriceHistory.objects.create(
            store_product_link=original_listing,
            price="99.90",
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
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
                    stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
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
        assert updated_listing.price_history.count() == 1

    def test_replace_listings_adds_history_only_when_price_or_stock_changes(
        self,
    ) -> None:
        """A new price history row should be appended only for meaningful changes."""
        listing = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="sku-1",
            product_link="https://growth.example/item",
        )
        ProductPriceHistory.objects.create(
            store_product_link=listing,
            price="99.90",
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_name="Growth",
                    external_id="sku-1",
                    product_link="https://growth.example/item",
                    price=109.90,
                    stock_status=ProductPriceHistory.StockStatus.LAST_UNITS,
                ),
            ],
        )

        listing.refresh_from_db()
        latest_history = listing.price_history.first()
        assert listing.price_history.count() == self.UPDATED_HISTORY_COUNT
        assert latest_history is not None
        assert latest_history.price == self.UPDATED_PRICE
        assert latest_history.stock_status == ProductPriceHistory.StockStatus.LAST_UNITS

    def test_replace_listings_deletes_removed_store_links(self) -> None:
        """Listings omitted from the desired state should be removed."""
        retained_listing = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="growth-1",
            product_link="https://growth.example/item",
        )
        removed_listing = ProductStore.objects.create(
            product=self.product,
            store=self.other_store,
            external_id="dux-1",
            product_link="https://dux.example/item",
        )
        ProductPriceHistory.objects.create(
            store_product_link=retained_listing,
            price="99.90",
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
        )
        ProductPriceHistory.objects.create(
            store_product_link=removed_listing,
            price="89.90",
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
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
        assert product.brand.name == "Growth"
        assert product.category is not None
        assert product.category.name == "Protein"
        assert product.tags.count() == self.EXPECTED_TAG_COUNT
        assert product.store_links.count() == 1
        assert product.nutrition_profiles.count() == 1
        listing = product.store_links.first()
        assert listing is not None
        assert listing.price_history.count() == 1

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

    def test_execute_links_origin_scraped_item_to_created_store_listing(self) -> None:
        """Origin scraped items should be linked during product creation."""
        page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/whey",
        )
        origin_item = ScrapedItem.objects.create(
            store_slug="growth",
            external_id="growth-origin-900",
            name="Whey Isolate",
            price=Decimal("149.90"),
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
            source_page=page,
        )

        product = self.service.execute(
            ProductCreateInput(
                name="Whey Isolate",
                weight=900,
                brand_name="Growth",
                origin_scraped_item_id=origin_item.id,
                stores=[
                    StoreListingPayload(
                        store_name="Growth",
                        external_id="growth-900",
                        product_link="https://growth.example/whey",
                        price=149.90,
                    ),
                ],
            ),
        )

        origin_item.refresh_from_db()
        listing = product.store_links.get(store=self.store)

        assert origin_item.product_store_id == listing.id
        assert origin_item.status == ScrapedItem.Status.LINKED

    def test_execute_reuses_existing_origin_listing_on_retry(self) -> None:
        """Retries should link to an existing listing without duplicating products."""
        brand = Brand.objects.create(name="growth", display_name="Growth")
        existing_product = Product.objects.create(
            name="Whey Isolate",
            weight=900,
            brand=brand,
            ean="7890000000001",
        )
        existing_listing = ProductStore.objects.create(
            product=existing_product,
            store=self.store,
            external_id="growth-900",
            product_link="https://growth.example/whey",
        )
        origin_item = ScrapedItem.objects.create(
            store_slug="growth",
            external_id="growth-origin-900",
            name="Whey Isolate",
            price=Decimal("149.90"),
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
        )

        product = self.service.execute(
            ProductCreateInput(
                name="Whey Isolate Updated",
                weight=900,
                brand_name="Growth",
                ean="7890000000001",
                origin_scraped_item_id=origin_item.id,
                stores=[
                    StoreListingPayload(
                        store_name="Growth",
                        external_id="growth-900",
                        product_link="https://growth.example/whey",
                        price=149.90,
                    ),
                ],
            ),
        )

        origin_item.refresh_from_db()

        assert product.id == existing_product.id
        assert Product.objects.count() == 1
        assert origin_item.product_store_id == existing_listing.id
        assert origin_item.status == ScrapedItem.Status.LINKED

    def test_execute_rejects_origin_link_without_matching_store_listing(self) -> None:
        """Origin links should fail when no target listing can be resolved."""
        origin_item = ScrapedItem.objects.create(
            store_slug="growth",
            external_id="growth-origin-900",
            name="Whey Isolate",
        )

        raised_validation_error = False

        try:
            self.service.execute(
                ProductCreateInput(
                    name="Whey Isolate",
                    weight=900,
                    brand_name="Growth",
                    origin_scraped_item_id=origin_item.id,
                    stores=[
                        StoreListingPayload(
                            store_name="Dux",
                            external_id="dux-900",
                            product_link="https://dux.example/whey",
                            price=149.90,
                        ),
                        StoreListingPayload(
                            store_name="Integralmedica",
                            external_id="integral-900",
                            product_link="https://integral.example/whey",
                            price=159.90,
                        ),
                    ],
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

    def test_execute_updates_content_category_tags_and_enrichment_timestamp(
        self,
    ) -> None:
        """Metadata updates should apply resolved taxonomy and timestamp enrichment."""
        previous_enriched_at = self.product.last_enriched_at

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
        assert updated_product.last_enriched_at != previous_enriched_at

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

    def test_apply_selection_switches_between_existing_new_and_none(self) -> None:
        """Nutrition selection should support existing, new, and clear flows."""
        self.service.apply_selection(
            self.product,
            nutrition_mode=ProductNutritionService.MODE_EXISTING,
            existing_facts=self.existing_facts,
        )
        existing_profile = self.product.nutrition_profiles.first()
        assert existing_profile is not None
        assert existing_profile.nutrition_facts == self.existing_facts

        self.service.apply_selection(
            self.product,
            nutrition_mode=ProductNutritionService.MODE_NEW,
            nutrition_profiles_data=[
                ProductNutritionPayload(
                    nutrition_facts=NutritionFactsPayload(
                        description="New table",
                        serving_size_grams=40,
                        energy_kcal=150,
                        proteins=30,
                        carbohydrates=4,
                        total_fats=3,
                    ),
                ),
            ],
        )
        new_profile = self.product.nutrition_profiles.first()
        assert new_profile is not None
        assert new_profile.nutrition_facts.description == "New table"

        self.service.apply_selection(
            self.product,
            nutrition_mode=ProductNutritionService.MODE_NONE,
        )
        assert self.product.nutrition_profiles.count() == 0

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

        facts = NutritionFacts.objects.get()
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
        self.store_link = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="568",
            product_link="https://example.com/whey",
        )
        self.price_history = ProductPriceHistory.objects.create(
            store_product_link=self.store_link,
            price=Decimal("72.90"),
        )

    def test_delete_products_with_related_data_removes_related_records(self) -> None:
        """Admin action should remove related price history and store links."""
        request = self.factory.post("/admin/core/product/")

        self.admin.delete_products_with_related_data(
            request,
            Product.objects.filter(id=self.product.id),
        )

        assert Product.objects.filter(id=self.product.id).count() == 0
        assert ProductStore.objects.filter(id=self.store_link.id).count() == 0
        assert ProductPriceHistory.objects.filter(id=self.price_history.id).count() == 0
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

        self.link = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            product_link="https://example.com",
        )
        ProductPriceHistory.objects.create(
            store_product_link=self.link,
            price=Decimal("100.00"),
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
        """Latest price annotations should stay consistent under collected_at ties."""
        second_store = Store.objects.create(
            name="Second Store",
            display_name="Second Store",
        )
        second_link = ProductStore.objects.create(
            product=self.product,
            store=second_store,
            product_link="https://example.com/second",
        )

        first_history = ProductPriceHistory.objects.create(
            store_product_link=self.link,
            price=Decimal("100.00"),
        )
        second_history = ProductPriceHistory.objects.create(
            store_product_link=second_link,
            price=Decimal("150.00"),
        )
        tied_timestamp = timezone.now()
        ProductPriceHistory.objects.filter(
            id__in=[first_history.id, second_history.id],
        ).update(collected_at=tied_timestamp)

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

        alpha_store = ProductStore.objects.create(
            product=alpha,
            store=self.store,
            product_link="https://example.com/alpha",
        )
        beta_store = ProductStore.objects.create(
            product=beta,
            store=self.store,
            product_link="https://example.com/beta",
        )
        ProductPriceHistory.objects.create(
            store_product_link=alpha_store,
            price=Decimal("100.00"),
        )
        ProductPriceHistory.objects.create(
            store_product_link=beta_store,
            price=Decimal("100.00"),
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


class GraphQLProductCreateTests(TestCase):
    """Tests for the product creation mutation."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.factory = RequestFactory()
        self.api_key_obj = APIKey.objects.create(name="Test Client")
        self.valid_key = self.api_key_obj.key
        self.view = GraphQLView.as_view(schema=schema)
        self.page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/whey",
        )
        self.origin_item = ScrapedItem.objects.create(
            store_slug="growth",
            external_id="growth-origin-900",
            name="Whey Isolate",
            price=Decimal("149.90"),
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
            source_page=self.page,
        )

    def test_create_product_accepts_origin_scraped_item_id(self) -> None:
        """The mutation should link the origin scraped item when provided."""
        mutation = """
        mutation CreateProduct($data: ProductInput!) {
          createProduct(data: $data) {
            product {
              id
              storeLinks {
                id
              }
            }
            errors {
              field
              message
            }
          }
        }
        """
        variables = {
            "data": {
                "name": "Whey Isolate",
                "weight": 900,
                "brandName": "Growth",
                "originScrapedItemId": self.origin_item.id,
                "stores": [
                    {
                        "storeName": "Growth",
                        "externalId": "growth-900",
                        "productLink": "https://growth.example/whey",
                        "price": 149.9,
                        "stockStatus": "AVAILABLE",
                    },
                ],
            },
        }
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": mutation, "variables": variables}),
            content_type="application/json",
            HTTP_X_API_KEY=self.valid_key,
        )

        response = cast("HttpResponse", self.view(request))
        payload = json.loads(response.content)

        self.origin_item.refresh_from_db()
        assert payload["data"]["createProduct"]["errors"] is None
        assert payload["data"]["createProduct"]["product"]["id"] is not None
        assert self.origin_item.product_store_id is not None
        assert self.origin_item.status == ScrapedItem.Status.LINKED

    def test_create_product_reuses_existing_origin_listing_on_retry(self) -> None:
        """The mutation should be idempotent for already-published origin listings."""
        store = Store.objects.create(name="growth", display_name="Growth")
        brand = Brand.objects.create(name="growth", display_name="Growth")
        existing_product = Product.objects.create(
            name="Whey Isolate",
            weight=900,
            brand=brand,
            ean="7890000000001",
        )
        existing_listing = ProductStore.objects.create(
            product=existing_product,
            store=store,
            external_id="growth-900",
            product_link="https://growth.example/whey",
        )
        mutation = """
        mutation CreateProduct($data: ProductInput!) {
          createProduct(data: $data) {
            product {
              id
            }
            errors {
              field
              message
            }
          }
        }
        """
        variables = {
            "data": {
                "name": "Whey Isolate Updated",
                "weight": 900,
                "brandName": "Growth",
                "ean": "7890000000001",
                "originScrapedItemId": self.origin_item.id,
                "stores": [
                    {
                        "storeName": "Growth",
                        "externalId": "growth-900",
                        "productLink": "https://growth.example/whey",
                        "price": 149.9,
                        "stockStatus": "AVAILABLE",
                    },
                ],
            },
        }
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": mutation, "variables": variables}),
            content_type="application/json",
            HTTP_X_API_KEY=self.valid_key,
        )

        response = cast("HttpResponse", self.view(request))
        payload = json.loads(response.content)
        self.origin_item.refresh_from_db()

        assert payload["data"]["createProduct"]["errors"] is None
        assert Product.objects.count() == 1
        assert self.origin_item.product_store_id == existing_listing.id
        assert self.origin_item.status == ScrapedItem.Status.LINKED

    def test_create_product_accepts_rich_combo_component_payload(self) -> None:
        """The mutation should accept full combo component payloads."""
        mutation = """
        mutation CreateProduct($data: ProductInput!) {
          createProduct(data: $data) {
            product {
              id
            }
            errors {
              field
              message
            }
          }
        }
        """
        variables = {
            "data": {
                "name": "Combo Whey + Creatina",
                "weight": 1200,
                "brandName": "Growth",
                "isCombo": True,
                "components": [
                    {
                        "name": "Creatina",
                        "weight": 300,
                        "brandName": "Growth",
                        "categoryPath": ["Energy", "Creatine"],
                        "description": "Creatina do combo",
                        "packaging": "REFILL",
                        "stores": [
                            {
                                "storeName": "Growth",
                                "externalId": "creatina-300",
                                "productLink": "https://growth.example/creatina-300",
                                "price": 79.9,
                                "stockStatus": "AVAILABLE",
                            },
                        ],
                    },
                ],
            },
        }
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": mutation, "variables": variables}),
            content_type="application/json",
            HTTP_X_API_KEY=self.valid_key,
        )

        response = cast("HttpResponse", self.view(request))
        payload = json.loads(response.content)

        created_component = Product.objects.get(name="Creatina", weight=300)
        assert payload["data"]["createProduct"]["errors"] is None
        assert payload["data"]["createProduct"]["product"]["id"] is not None
        assert created_component.packaging == Product.Packaging.REFILL
        assert created_component.store_links.count() == 1


class GraphQLSecurityTests(TestCase):
    """Tests for GraphQL API security."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.factory = RequestFactory()
        self.api_key_obj = APIKey.objects.create(name="Test Client")
        self.valid_key = self.api_key_obj.key
        self.view = GraphQLView.as_view(schema=schema)

    def _execute_query(
        self,
        query: str = "{ hello }",
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        """Execute the hello query and decode the JSON response."""
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": query}),
            content_type="application/json",
            **headers if headers else {},
        )
        response = self.view(request)
        if hasattr(response, "content"):
            return json.loads(cast("HttpResponse", response).content)
        return json.loads(b"{}")

    def test_query_without_api_key(self) -> None:
        """Internal requests without API key should be denied."""
        result = self._execute_query()
        assert "errors" in result
        assert result["errors"][0]["message"] == "API Key required"

    def test_public_catalog_query_without_api_key(self) -> None:
        """GraphQL catalog requests without API key should be denied."""
        result = self._execute_query(
            """
            {
              catalogProducts {
                pageInfo {
                  totalCount
                }
                items {
                  id
                }
              }
            }
            """,
        )
        assert "errors" in result
        assert result["errors"][0]["message"] == "API Key required"

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

    def test_subscribe_alerts_query_without_api_key(self) -> None:
        """GraphQL alert subscriptions without API key should be denied."""
        result = self._execute_query(
            """
            mutation {
              subscribeAlerts(email: "user@example.com") {
                success
              }
            }
            """,
        )
        assert "errors" in result
        assert result["errors"][0]["message"] == "API Key required"

    def test_query_with_valid_api_key(self) -> None:
        """Requests with valid API key should be allowed."""
        result = self._execute_query(headers={"HTTP_X_API_KEY": self.valid_key})
        assert "data" in result
        assert result["data"]["hello"] == "Baboom GraphQL API is Online"

    def test_query_with_invalid_api_key(self) -> None:
        """Requests with invalid API key should be denied."""
        result = self._execute_query(headers={"HTTP_X_API_KEY": "invalid-key"})
        assert "errors" in result
        assert result["errors"][0]["message"] == "API Key required"

    def test_query_with_disabled_api_key(self) -> None:
        """Requests with disabled API key should be denied."""
        self.api_key_obj.is_active = False
        self.api_key_obj.save()

        result = self._execute_query(headers={"HTTP_X_API_KEY": self.valid_key})
        assert "errors" in result
        assert result["errors"][0]["message"] == "API Key required"
