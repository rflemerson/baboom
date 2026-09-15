"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.dtos import (
    ProductCreateInput,
    ProductMetadataUpdateInput,
    StoreListingPayload,
)
from core.models import (
    Brand,
    Category,
    Product,
    Store,
    Tag,
)
from core.services import (
    ProductCreateService,
    ProductMetadataUpdateService,
)
from core.tests.helpers import (
    _grams,
)


class ProductCreateServiceTests(TestCase):
    """Essential coverage for product creation workflows."""

    EXPECTED_TAG_COUNT = 2

    def setUp(self) -> None:
        """Create reusable fixtures and services."""
        self.service = ProductCreateService()
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.store = Store.objects.create(name="growth", display_name="Growth")

    def test_execute_creates_product_with_taxonomy_and_store(self) -> None:
        """Product creation should persist brand, category, tags and store listing."""
        supplements = Category.add_root(name="Supplements")
        protein = supplements.add_child(name="Protein")
        goal = Tag.add_root(name="Goal")
        muscle = goal.add_child(name="Muscle")
        type_tag = Tag.add_root(name="Type")
        whey_tag = type_tag.add_child(name="Whey")

        product = self.service.execute(
            ProductCreateInput(
                name="Whey Isolate",
                net_mass=900,
                brand_id=self.brand.id,
                category_id=protein.id,
                ean="1234567890123",
                description="Lean whey isolate",
                is_published=True,
                tag_ids=[muscle.id, whey_tag.id],
                stores=[
                    StoreListingPayload(
                        store_id=self.store.id,
                        external_id="growth-900",
                        product_link="https://growth.example/whey",
                        price=149.90,
                    ),
                ],
            ),
        )

        product.refresh_from_db()
        assert product.brand.id == self.brand.id
        assert product.category is not None
        assert product.category.name == "Protein"
        assert product.tags.count() == self.EXPECTED_TAG_COUNT
        assert product.store_links.count() == 1
        listing = product.store_links.first()
        assert listing is not None
        assert listing.offer.price_observations.count() == 1

    def test_execute_rejects_unknown_brand(self) -> None:
        """Product creation should fail when the brand ID does not exist."""
        validation_error = None
        try:
            self.service.execute(
                ProductCreateInput(
                    name="Whey",
                    net_mass=900,
                    brand_id=99999,
                ),
            )
        except ValidationError as error:
            validation_error = error

        assert validation_error is not None
        assert "brand_id" in validation_error.message_dict

    def test_execute_rejects_duplicate_ean(self) -> None:
        """Product creation should reject duplicate EAN values."""
        Product.objects.create(
            name="Existing Whey",
            brand=self.brand,
            net_mass=_grams(900),
            ean="1234567890123",
            packaging=Product.Packaging.CONTAINER,
        )

        validation_error = None
        try:
            self.service.execute(
                ProductCreateInput(
                    name="Another Whey",
                    net_mass=900,
                    brand_id=self.brand.id,
                    ean="1234567890123",
                ),
            )
        except ValidationError as error:
            validation_error = error

        assert validation_error is not None
        assert "ean" in validation_error.message_dict


class ProductMetadataUpdateServiceTests(TestCase):
    """Essential coverage for product metadata updates."""

    EXPECTED_TAG_COUNT = 2
    UPDATED_MASS_GRAMS = 450

    def setUp(self) -> None:
        """Create a baseline product for metadata update tests."""
        self.service = ProductMetadataUpdateService()
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Old Whey",
            brand=self.brand,
            net_mass=_grams(900),
            packaging=Product.Packaging.CONTAINER,
            description="Old description",
        )

    def test_execute_updates_content_category_and_tags(
        self,
    ) -> None:
        """Metadata updates should apply resolved taxonomy."""
        supplements = Category.add_root(name="Supplements")
        protein = supplements.add_child(name="Protein")
        goal = Tag.add_root(name="Goal")
        muscle = goal.add_child(name="Muscle")
        type_tag = Tag.add_root(name="Type")
        whey_tag = type_tag.add_child(name="Whey")

        updated_product = self.service.execute(
            product_id=self.product.id,
            data=ProductMetadataUpdateInput(
                name="New Whey",
                description="New description",
                packaging=Product.Packaging.REFILL,
                category_id=protein.id,
                tag_ids=[muscle.id, whey_tag.id],
            ),
        )

        updated_product.refresh_from_db()
        assert updated_product.name == "New Whey"
        assert updated_product.description == "New description"
        assert updated_product.packaging == Product.Packaging.REFILL
        assert updated_product.category is not None
        assert updated_product.category.name == "Protein"
        assert updated_product.tags.count() == self.EXPECTED_TAG_COUNT

    def test_execute_updates_brand_mass_and_ean(self) -> None:
        """Manager-facing product edits should persist core product identity fields."""
        new_brand = Brand.objects.create(name="dux", display_name="Dux")

        updated_product = self.service.execute(
            product_id=self.product.id,
            data=ProductMetadataUpdateInput(
                brand_id=new_brand.id,
                net_mass=self.UPDATED_MASS_GRAMS,
                ean="7891234567890",
            ),
        )

        updated_product.refresh_from_db()
        assert updated_product.brand == new_brand
        assert updated_product.net_mass == _grams(self.UPDATED_MASS_GRAMS)
        assert updated_product.ean == "7891234567890"

    def test_execute_can_clear_category(self) -> None:
        """Passing category_id=None explicitly should remove the current category."""
        category = Category.add_root(name="Supplements")
        self.product.category = category
        self.product.save()

        updated_product = self.service.execute(
            product_id=self.product.id,
            data=ProductMetadataUpdateInput(category_id=None),
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
