"""Application services for core catalog and alert workflows."""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

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
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
    Tag,
)

from .combo_resolution import ComboResolutionService
from .enrichment import EnrichmentService

if TYPE_CHECKING:
    from .types import ProductContentUpdateInput, ProductCreateInput

logger = logging.getLogger(__name__)


def alert_subscriber_create(*, email: str) -> AlertSubscriber:
    """Create a new alert subscriber."""
    subscriber = AlertSubscriber(email=email)
    subscriber.full_clean()
    subscriber.save()

    logger.info("New subscriber created: %s", email)

    return subscriber


def product_create(data: ProductCreateInput) -> Product:
    """Create a product with all related data (nested creation).

    Raises:
        ValidationError: If business rules are violated (e.g. duplicate EAN).

    """
    if data.ean and Product.objects.filter(ean=data.ean).exists():
        raise ValidationError({"ean": _("A product with this EAN already exists.")})

    try:
        with transaction.atomic():
            # 1. Brand
            brand, _created = Brand.objects.get_or_create(
                name=data.brand_name,
                defaults={"display_name": data.brand_name},
            )

            # 2. Category
            category = _resolve_category(data.category_name)

            # 3. Product
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

            # 4. Tags
            if data.tags:
                tag_objects = _resolve_tags(data.tags)
                product.tags.set(tag_objects)

            # 5. Stores & Prices
            if data.stores:
                _create_store_entries(product, data.stores)

            # 6. Combo Resolution or Nutrition Profiles
            if data.is_combo and data.components:
                ComboResolutionService().resolve_combo_components(
                    product,
                    data.components,
                )
            elif data.nutrition:
                # Only create direct nutrition profiles for Simple products
                # Or if Combo has explicit nutrition override (future proofing)
                _handle_nutrition_creation(product, data.nutrition)

            # 7. Enrichment (Auto-tagging sources)
            EnrichmentService().enrich_product(
                product,
                extra_claims=data.nutrient_claims,
            )

            return product

    except IntegrityError as e:
        raise ValidationError({"unknown": str(e)}) from e


def _resolve_category(category_name: str | list[str] | None) -> Category | None:
    """Resolve category from name string or path list."""
    if not category_name:
        return None

    # Support both string and list for backward compatibility/flexibility
    category_path = [category_name] if isinstance(category_name, str) else category_name

    category = None
    parent = None
    for cat_part in category_path:
        category = Category.objects.filter(name=cat_part).first()
        if not category:
            if parent:
                category = parent.add_child(name=cat_part)
            else:
                category = Category.add_root(name=cat_part)
        parent = category
    return category


def _resolve_tags(tags: list[str] | list[list[str]]) -> list[Tag]:
    """Resolve list of tags (simple or hierarchical) to Tag objects."""
    tag_objects = []
    # tags can be a list of strings (legacy) or a list of lists (new hierarchy)
    for tag_entry in tags:
        tag_path = [tag_entry] if isinstance(tag_entry, str) else tag_entry

        parent = None
        last_tag = None
        for tag_part in tag_path:
            tag = Tag.objects.filter(name=tag_part).first()
            if not tag:
                if parent:
                    tag = parent.add_child(name=tag_part)
                else:
                    tag = Tag.add_root(name=tag_part)
            parent = tag
            last_tag = tag

        if last_tag:
            tag_objects.append(last_tag)
    return tag_objects


def _create_store_entries(product: Product, stores: list[dict[str, Any]]) -> None:
    """Create Store, ProductStore link, and PriceHistory."""
    for store_data in stores:
        # Lookup by display_name to avoid unique constraint issues with slugs
        store, _created = Store.objects.get_or_create(
            display_name=store_data["store_name"],
            defaults={"name": slugify(store_data["store_name"])},
        )

        product_store = ProductStore.objects.create(
            product=product,
            store=store,
            external_id=store_data.get("external_id", ""),
            product_link=store_data["product_link"],
            affiliate_link=store_data.get("affiliate_link", ""),
        )

        ProductPriceHistory.objects.create(
            store_product_link=product_store,
            price=Decimal(str(store_data["price"])),
            stock_status=store_data.get("stock_status", "A"),
        )


@dataclass(slots=True)
class ProductContentUpdateResolved:
    """Resolved metadata updates ready to be applied to a product."""

    name: str | None
    description: str | None
    packaging: str | None
    category: Category | None
    replace_category: bool
    tags: list[Tag] | None


def _resolve_update_category(category_name: str | None) -> tuple[Category | None, bool]:
    """Resolve the category update and whether it should replace current value."""
    if category_name is None:
        return None, False
    if category_name == "":
        return None, True

    category = Category.objects.filter(name=category_name).first()
    if not category:
        category = Category.add_root(name=category_name)
    return category, True


def _resolve_update_tags(tags: list[str] | None) -> list[Tag] | None:
    """Resolve flat tag names into persisted Tag objects."""
    if tags is None:
        return None

    tag_objects = []
    for tag_name in tags:
        tag = Tag.objects.filter(name=tag_name).first()
        if not tag:
            tag = Tag.add_root(name=tag_name)
        tag_objects.append(tag)
    return tag_objects


def _resolve_product_content_update(
    data: ProductContentUpdateInput,
) -> ProductContentUpdateResolved:
    """Resolve category and tag references for a product content update."""
    category, replace_category = _resolve_update_category(data.category_name)
    return ProductContentUpdateResolved(
        name=data.name,
        description=data.description,
        packaging=data.packaging,
        category=category,
        replace_category=replace_category,
        tags=_resolve_update_tags(data.tags),
    )


def _apply_product_content_update(
    product: Product,
    resolved: ProductContentUpdateResolved,
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


def product_update_content(
    *,
    product: Product,
    data: ProductContentUpdateInput,
) -> Product:
    """Update product metadata without modifying price data."""
    try:
        with transaction.atomic():
            resolved = _resolve_product_content_update(data)
            _apply_product_content_update(product, resolved)
            product.last_enriched_at = timezone.now()
            product.save()

            return product

    except IntegrityError as e:
        raise ValidationError({"unknown": str(e)}) from e


def _handle_nutrition_creation(
    product: Product,
    nutrition_list: list[dict[str, Any]],
) -> None:
    """Handle the complex logic of creating/linking nutrition profiles.

    Creates facts, micronutrients, and flavors.
    """
    for nutr_data in nutrition_list:
        facts_data = nutr_data["nutrition_facts"]
        micros_data = facts_data.get("micronutrients") or []

        # --- CENTRALIZED HASH LOGIC ---
        # Now we call the Model to calculate the hash.
        # We pass the dict and list of micros explicitly.
        content_hash = NutritionFacts.generate_hash(
            source=facts_data,
            micronutrients=micros_data,
        )
        # -------------------------------

        defaults = {
            "description": facts_data.get("description", ""),
            "serving_size_grams": facts_data["serving_size_grams"],
            "energy_kcal": facts_data["energy_kcal"],
            "proteins": Decimal(str(facts_data["proteins"])),
            "carbohydrates": Decimal(str(facts_data["carbohydrates"])),
            "total_sugars": Decimal(str(facts_data.get("total_sugars", 0))),
            "added_sugars": Decimal(str(facts_data.get("added_sugars", 0))),
            "total_fats": Decimal(str(facts_data["total_fats"])),
            "saturated_fats": Decimal(str(facts_data.get("saturated_fats", 0))),
            "trans_fats": Decimal(str(facts_data.get("trans_fats", 0))),
            "dietary_fiber": Decimal(str(facts_data.get("dietary_fiber", 0))),
            "sodium": Decimal(str(facts_data.get("sodium", 0))),
        }

        facts, created = NutritionFacts.objects.get_or_create(
            content_hash=content_hash,
            defaults=defaults,
        )

        # Bulk create micronutrients only if facts was just created
        if created and micros_data:
            micros = [
                Micronutrient(
                    nutrition_facts=facts,
                    name=m["name"],
                    value=Decimal(str(m["value"])),
                    unit=m.get("unit", "mg"),
                )
                for m in micros_data
            ]
            Micronutrient.objects.bulk_create(micros)

        # Smart grouping
        profile, _created = ProductNutrition.objects.get_or_create(
            product=product,
            nutrition_facts=facts,
        )

        # Add flavors
        flavor_names = nutr_data.get("flavor_names")
        if flavor_names:
            for flav_name in flavor_names:
                flavor, _created = Flavor.objects.get_or_create(name=flav_name)
                profile.flavors.add(flavor)
