"""Application services for core catalog and alert workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import (
    AlertSubscriber,
    Brand,
    Category,
    Flavor,
    Micronutrient,
    NutritionFacts,
    Product,
    ProductComponent,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
    Tag,
)
from scrapers.models import ScrapedItem
from scrapers.services import ScraperService

if TYPE_CHECKING:
    from core.types import (
        MicronutrientPayload,
        NutritionFactsPayload,
        ProductComponentInput,
        ProductCreateInput,
        ProductMetadataUpdateInput,
        ProductNutritionPayload,
        ProductStorePayload,
    )

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AlertSubscriptionResult:
    """Outcome of an alert subscription attempt."""

    email: str
    subscriber: AlertSubscriber | None
    already_subscribed: bool


class AlertSubscriptionService:
    """Validate and subscribe emails to price alerts."""

    def execute(self, *, email: str) -> AlertSubscriptionResult:
        """Normalize, validate, and create an alert subscription."""
        normalized_email = self._normalize_email(email)
        if self._is_already_subscribed(normalized_email):
            return AlertSubscriptionResult(
                email=normalized_email,
                subscriber=None,
                already_subscribed=True,
            )

        subscriber = AlertSubscriber(email=normalized_email)
        subscriber.full_clean()
        subscriber.save()

        logger.info("New subscriber created: %s", normalized_email)
        return AlertSubscriptionResult(
            email=normalized_email,
            subscriber=subscriber,
            already_subscribed=False,
        )

    def _normalize_email(self, email: str) -> str:
        """Normalize incoming email values before validation."""
        return email.strip().lower()

    def _is_already_subscribed(self, email: str) -> bool:
        """Return whether a subscription already exists for the email."""
        return AlertSubscriber.objects.filter(email=email).exists()


class ComboResolutionService:
    """Resolve combo components to existing products or placeholders."""

    def resolve_combo_components(
        self,
        parent_product: Product,
        components_data: list[ProductComponentInput],
    ) -> list[ProductComponent]:
        """Resolve component DTOs to concrete component links."""
        created_links = []
        parent_product.component_links.all().delete()

        for component_data in components_data:
            component_product = self._find_best_match(parent_product, component_data)
            if component_product is None:
                component_product = self._create_placeholder(
                    component_data,
                    parent_product,
                )

            created_links.append(
                ProductComponent.objects.create(
                    parent=parent_product,
                    component=component_product,
                    quantity=component_data.quantity,
                ),
            )

        return created_links

    def _find_best_match(
        self,
        parent_product: Product,
        component_data: ProductComponentInput,
    ) -> Product | None:
        """Resolve a component using exact identifiers only."""
        return (
            self._match_by_ean(component_data.ean)
            or self._match_by_external_id(
                parent_product,
                component_data.external_id,
            )
        )

    def _match_by_ean(self, ean: str | None) -> Product | None:
        """Match a simple product by its global identifier."""
        if not ean:
            return None

        return Product.objects.filter(
            ean=ean,
            type=Product.Type.SIMPLE,
        ).first()

    def _match_by_external_id(
        self,
        parent_product: Product,
        external_id: str | None,
    ) -> Product | None:
        """Match a simple product by store identifier within the combo context."""
        if not external_id:
            return None

        store_ids = list(
            parent_product.store_links.values_list("store_id", flat=True),
        )
        if not store_ids:
            return None

        return (
            Product.objects.filter(
                type=Product.Type.SIMPLE,
                brand_id=parent_product.brand_id,
                store_links__external_id=external_id,
                store_links__store_id__in=store_ids,
            )
            .distinct()
            .first()
        )

    def _create_placeholder(
        self,
        component_data: ProductComponentInput,
        parent_product: Product,
    ) -> Product:
        """Create an unpublished placeholder when no component match is found."""
        return Product.objects.create(
            name=f"[Placeholder] {component_data.name}",
            brand=parent_product.brand,
            weight=0,
            description=(
                "Auto-generated placeholder for component of "
                f"{parent_product.name}"
            ),
            is_published=False,
        )


class ProductNutritionService:
    """Attach typed nutrition profiles to a product."""

    def attach_profiles(
        self,
        product: Product,
        nutrition_profiles_data: list[ProductNutritionPayload],
    ) -> None:
        """Create or reuse nutrition profiles linked to a product."""
        for profile_data in nutrition_profiles_data:
            facts_payload = profile_data.nutrition_facts
            micronutrient_payloads = facts_payload.micronutrients or []

            facts, created = self._get_or_create_facts_by_content_hash(
                facts_payload,
                micronutrient_payloads,
            )
            self._create_micronutrients_if_needed(
                facts,
                facts_were_created=created,
                micronutrient_payloads=micronutrient_payloads,
            )
            profile = self._get_or_create_profile(product, facts)
            self._attach_flavors(profile, profile_data.flavor_names)

    def _get_or_create_facts_by_content_hash(
        self,
        facts_payload: NutritionFactsPayload,
        micronutrient_payloads: list[MicronutrientPayload],
    ) -> tuple[NutritionFacts, bool]:
        """Create or reuse nutrition facts based on their content hash."""
        content_hash = NutritionFacts.generate_hash(
            source=facts_payload.model_dump(exclude={"micronutrients"}),
            micronutrients=[
                micronutrient_payload.model_dump()
                for micronutrient_payload in micronutrient_payloads
            ],
        )
        return NutritionFacts.objects.get_or_create(
            content_hash=content_hash,
            defaults=self._build_facts_defaults(facts_payload),
        )

    def _build_facts_defaults(
        self,
        facts_payload: NutritionFactsPayload,
    ) -> dict[str, str | int | float | Decimal]:
        """Build defaults used when persisting new nutrition facts."""
        return {
            "description": facts_payload.description or "",
            "serving_size_grams": facts_payload.serving_size_grams,
            "energy_kcal": facts_payload.energy_kcal,
            "proteins": Decimal(str(facts_payload.proteins)),
            "carbohydrates": Decimal(str(facts_payload.carbohydrates)),
            "total_sugars": Decimal(str(facts_payload.total_sugars)),
            "added_sugars": Decimal(str(facts_payload.added_sugars)),
            "total_fats": Decimal(str(facts_payload.total_fats)),
            "saturated_fats": Decimal(str(facts_payload.saturated_fats)),
            "trans_fats": Decimal(str(facts_payload.trans_fats)),
            "dietary_fiber": Decimal(str(facts_payload.dietary_fiber)),
            "sodium": Decimal(str(facts_payload.sodium)),
        }

    def _create_micronutrients_if_needed(
        self,
        facts: NutritionFacts,
        *,
        facts_were_created: bool,
        micronutrient_payloads: list[MicronutrientPayload],
    ) -> None:
        """Persist micronutrients only when facts are being created."""
        if not facts_were_created or not micronutrient_payloads:
            return

        Micronutrient.objects.bulk_create(
            [
                Micronutrient(
                    nutrition_facts=facts,
                    name=micronutrient_payload.name,
                    value=Decimal(str(micronutrient_payload.value)),
                    unit=micronutrient_payload.unit,
                )
                for micronutrient_payload in micronutrient_payloads
            ],
        )

    def _get_or_create_profile(
        self,
        product: Product,
        facts: NutritionFacts,
    ) -> ProductNutrition:
        """Create or reuse the link between a product and nutrition facts."""
        profile, _created = ProductNutrition.objects.get_or_create(
            product=product,
            nutrition_facts=facts,
        )
        return profile

    def _attach_flavors(
        self,
        profile: ProductNutrition,
        flavor_names: list[str] | None,
    ) -> None:
        """Attach flavor names to a nutrition profile."""
        if not flavor_names:
            return

        for flavor_name in flavor_names:
            flavor, _created = Flavor.objects.get_or_create(name=flavor_name)
            profile.flavors.add(flavor)


class ScrapedItemLinkService:
    """Link an origin scraped item to the product created from it."""

    def link_created_product(
        self,
        *,
        product: Product,
        origin_scraped_item_id: int | None,
    ) -> None:
        """Link and sync the originating scraped item when available."""
        if origin_scraped_item_id is None:
            return

        item = ScrapedItem.objects.filter(id=origin_scraped_item_id).first()
        if item is None:
            return

        linked_store = self._find_linked_store(product, item)
        if linked_store is None:
            return

        item.product_store = linked_store
        item.status = ScrapedItem.Status.LINKED
        item.save(update_fields=["product_store", "status"])
        ScraperService.sync_price_to_core(item)

    def _find_linked_store(
        self,
        product: Product,
        item: ScrapedItem,
    ) -> ProductStore | None:
        """Find the most appropriate store link for the scraped origin item."""
        linked_store = self._match_store_link_by_identity(product, item)
        if linked_store is not None:
            return linked_store

        source_url = item.source_page.url if item.source_page else ""
        if source_url:
            linked_store = ProductStore.objects.filter(
                product=product,
                product_link=source_url,
            ).first()
            if linked_store is not None:
                return linked_store

        return ProductStore.objects.filter(product=product).first()

    def _match_store_link_by_identity(
        self,
        product: Product,
        item: ScrapedItem,
    ) -> ProductStore | None:
        """Match the store link by store identity and external identifier."""
        if not item.external_id:
            return None

        return ProductStore.objects.filter(
            product=product,
            store__name=item.store_slug,
            external_id=item.external_id,
        ).first()


class ProductCreateService:
    """Create products and their related catalog records."""

    def execute(self, data: ProductCreateInput) -> Product:
        """Create a product with all related data."""
        self._validate_unique_ean(data.ean)

        try:
            with transaction.atomic():
                brand = self._resolve_brand(data.brand_name)
                category = self._resolve_category(data.category_name)

                product = Product.objects.create(
                    name=data.name,
                    weight=data.weight,
                    brand=brand,
                    category=category,
                    ean=data.ean,
                    description=data.description or "",
                    packaging=data.packaging,
                    is_published=data.is_published,
                    type=Product.Type.COMBO if data.is_combo else Product.Type.SIMPLE,
                )

                if data.tags:
                    product.tags.set(self._resolve_tags(data.tags))

                if data.stores:
                    self._create_store_entries(product, data.stores)

                if data.is_combo and data.components:
                    ComboResolutionService().resolve_combo_components(
                        product,
                        data.components,
                    )
                elif data.nutrition:
                    ProductNutritionService().attach_profiles(product, data.nutrition)

                ScrapedItemLinkService().link_created_product(
                    product=product,
                    origin_scraped_item_id=data.origin_scraped_item_id,
                )

                return product

        except IntegrityError as error:
            raise ValidationError({"unknown": str(error)}) from error

    def _validate_unique_ean(self, ean: str | None) -> None:
        """Reject duplicate EAN values before creating the product."""
        if ean and Product.objects.filter(ean=ean).exists():
            raise ValidationError({"ean": _("A product with this EAN already exists.")})

    def _resolve_brand(self, brand_name: str) -> Brand:
        """Find or create the brand associated with the product."""
        brand, _created = Brand.objects.get_or_create(
            name=brand_name,
            defaults={"display_name": brand_name},
        )
        return brand

    def _resolve_category(
        self,
        category_name: str | list[str] | None,
    ) -> Category | None:
        """Resolve a category from a flat name or hierarchical path."""
        if not category_name:
            return None

        category_path = (
            [category_name] if isinstance(category_name, str) else category_name
        )

        category = None
        parent = None
        for category_part in category_path:
            category = Category.objects.filter(name=category_part).first()
            if not category:
                category = (
                    parent.add_child(name=category_part)
                    if parent
                    else Category.add_root(name=category_part)
                )
            parent = category
        return category

    def _resolve_tags(self, tags: list[str] | list[list[str]]) -> list[Tag]:
        """Resolve flat or hierarchical tag inputs to persisted tags."""
        tag_objects = []
        for tag_entry in tags:
            tag_path = [tag_entry] if isinstance(tag_entry, str) else tag_entry

            parent = None
            last_tag = None
            for tag_part in tag_path:
                tag = Tag.objects.filter(name=tag_part).first()
                if not tag:
                    tag = parent.add_child(name=tag_part) if parent else Tag.add_root(
                        name=tag_part,
                    )
                parent = tag
                last_tag = tag

            if last_tag:
                tag_objects.append(last_tag)
        return tag_objects

    def _create_store_entries(
        self,
        product: Product,
        stores: list[ProductStorePayload],
    ) -> None:
        """Create store links and initial price history for a product."""
        for store_payload in stores:
            store, _created = Store.objects.get_or_create(
                display_name=store_payload.store_name,
                defaults={"name": slugify(store_payload.store_name)},
            )

            product_store = ProductStore.objects.create(
                product=product,
                store=store,
                external_id=store_payload.external_id or "",
                product_link=store_payload.product_link,
                affiliate_link=store_payload.affiliate_link or "",
            )

            ProductPriceHistory.objects.create(
                store_product_link=product_store,
                price=Decimal(str(store_payload.price)),
                stock_status=store_payload.stock_status,
            )


@dataclass(slots=True)
class ProductMetadataUpdateResolved:
    """Resolved metadata updates ready to be applied to a product."""

    name: str | None
    description: str | None
    packaging: str | None
    category: Category | None
    replace_category: bool
    tags: list[Tag] | None


class ProductMetadataUpdateService:
    """Apply metadata-only updates to existing products."""

    def execute(
        self,
        *,
        product_id: int,
        data: ProductMetadataUpdateInput,
    ) -> Product:
        """Update product metadata without modifying price data."""
        try:
            with transaction.atomic():
                product = self._get_product(product_id)
                resolved = self._resolve(data)
                self._apply(product, resolved)
                product.last_enriched_at = timezone.now()
                product.save()
                return product

        except IntegrityError as error:
            raise ValidationError({"unknown": str(error)}) from error

    def _resolve(
        self,
        data: ProductMetadataUpdateInput,
    ) -> ProductMetadataUpdateResolved:
        """Resolve category and tag references for a product content update."""
        category, replace_category = self._resolve_update_category(data.category_name)
        return ProductMetadataUpdateResolved(
            name=data.name,
            description=data.description,
            packaging=data.packaging,
            category=category,
            replace_category=replace_category,
            tags=self._resolve_update_tags(data.tags),
        )

    def _get_product(self, product_id: int) -> Product:
        """Load the product being updated or raise a validation error."""
        product = Product.objects.filter(id=product_id).first()
        if product is None:
            raise ValidationError({"product_id": _("Product not found")})
        return product

    def _apply(
        self,
        product: Product,
        resolved: ProductMetadataUpdateResolved,
    ) -> None:
        """Apply resolved metadata updates to the product instance."""
        if resolved.name is not None:
            product.name = resolved.name
        if resolved.description is not None:
            product.description = resolved.description
        if resolved.packaging is not None:
            product.packaging = resolved.packaging
        if resolved.replace_category:
            product.category = resolved.category
        if resolved.tags is not None:
            product.tags.set(resolved.tags)

    def _resolve_update_category(
        self,
        category_name: str | list[str] | None,
    ) -> tuple[Category | None, bool]:
        """Resolve the category update and whether it should replace current value."""
        if category_name is None:
            return None, False
        if category_name == "":
            return None, True

        category_path = (
            [category_name] if isinstance(category_name, str) else category_name
        )

        category = None
        parent = None
        for category_part in category_path:
            category = Category.objects.filter(name=category_part).first()
            if not category:
                category = (
                    parent.add_child(name=category_part)
                    if parent
                    else Category.add_root(name=category_part)
                )
            parent = category
        return category, True

    def _resolve_update_tags(
        self,
        tags: list[str] | list[list[str]] | None,
    ) -> list[Tag] | None:
        """Resolve flat or hierarchical tag inputs into persisted tags."""
        if tags is None:
            return None

        tag_objects = []
        for tag_entry in tags:
            tag_path = [tag_entry] if isinstance(tag_entry, str) else tag_entry

            parent = None
            last_tag = None
            for tag_part in tag_path:
                tag = Tag.objects.filter(name=tag_part).first()
                if not tag:
                    tag = parent.add_child(name=tag_part) if parent else Tag.add_root(
                        name=tag_part,
                    )
                parent = tag
                last_tag = tag

            if last_tag:
                tag_objects.append(last_tag)
        return tag_objects

