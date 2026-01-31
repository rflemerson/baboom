import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .models import (
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

if TYPE_CHECKING:
    from .models import AlertSubscriber

logger = logging.getLogger(__name__)


def alert_subscriber_create(*, email: str) -> AlertSubscriber:
    """
    Creates a new alert subscriber.
    """
    subscriber = AlertSubscriber(email=email)
    subscriber.full_clean()
    subscriber.save()

    logger.info(f"New subscriber created: {email}")

    return subscriber


def product_create(
    *,
    name: str,
    weight: int,
    brand_name: str,
    category_name: str | list[str] | None = None,
    ean: str | None = None,
    description: str | None = "",
    packaging: str = "CONTAINER",
    is_published: bool = False,
    tags: list[str] | list[list[str]] | None = None,
    stores: list[dict[str, Any]] | None = None,
    nutrition: list[dict[str, Any]] | None = None,
) -> Product:
    """
    Creates a product with all related data (nested creation).
    Raises ValidationError if business rules are violated.
    """
    if ean and Product.objects.filter(ean=ean).exists():
        raise ValidationError({"ean": _("A product with this EAN already exists.")})

    try:
        with transaction.atomic():
            # 1. Brand
            brand, _created = Brand.objects.get_or_create(
                name=brand_name,
                defaults={"display_name": brand_name},
            )

            # 2. Category (Hierarchical)
            category = None
            if category_name:
                # Support both string and list for backward compatibility/flexibility
                category_path = (
                    [category_name] if isinstance(category_name, str) else category_name
                )

                parent = None
                for cat_part in category_path:
                    category = Category.objects.filter(name=cat_part).first()
                    if not category:
                        if parent:
                            category = parent.add_child(name=cat_part)
                        else:
                            category = Category.add_root(name=cat_part)
                    parent = category

            # 3. Product
            product = Product.objects.create(
                name=name,
                weight=weight,
                brand=brand,
                category=category,
                ean=ean,
                description=description or "",
                packaging=packaging,
                is_published=is_published,
            )

            # 4. Tags (Hierarchical Paths)
            if tags:
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

                product.tags.set(tag_objects)

            # 5. Stores & Prices
            if stores:
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
                        affiliate_link=store_data.get("affiliate_link"),
                    )

                    ProductPriceHistory.objects.create(
                        store_product_link=product_store,
                        price=Decimal(str(store_data["price"])),
                        stock_status=store_data.get("stock_status", "A"),
                    )

            # 6. Nutrition Profiles
            if nutrition:
                _handle_nutrition_creation(product, nutrition)

            return product

    except IntegrityError as e:
        raise ValidationError({"unknown": str(e)}) from e


def product_update_content(
    *,
    product: Product,
    name: str | None = None,
    description: str | None = None,
    category_name: str | None = None,
    packaging: str | None = None,
    tags: list[str] | None = None,
) -> Product:
    """
    Updates product metadata (description, category, tags) without modifying price data.
    """
    try:
        with transaction.atomic():
            # Update basic fields if provided
            if name is not None:
                product.name = name
            if description is not None:
                product.description = description
            if packaging is not None:
                product.packaging = packaging

            # Update category
            if category_name is not None:
                if category_name == "":
                    product.category = None
                else:
                    category = Category.objects.filter(name=category_name).first()
                    if not category:
                        category = Category.add_root(name=category_name)
                    product.category = category

            # Update tags
            if tags is not None:
                tag_objects = []
                for tag_name in tags:
                    tag = Tag.objects.filter(name=tag_name).first()
                    if not tag:
                        tag = Tag.add_root(name=tag_name)
                    tag_objects.append(tag)
                # This replaces all tags, which seems to be the intended behavior for "syncing"
                product.tags.set(tag_objects)

            # Mark as enriched by LLM
            product.last_enriched_at = timezone.now()
            product.save()

            return product

    except IntegrityError as e:
        raise ValidationError({"unknown": str(e)}) from e


def _handle_nutrition_creation(
    product: Product, nutrition_list: list[dict[str, Any]]
) -> None:
    """
    Handles the complex logic of creating/linking nutrition profiles, facts,
    micronutrients, and flavors to a product.
    """
    for nutr_data in nutrition_list:
        facts_data = nutr_data["nutrition_facts"]
        micros_data = facts_data.get("micronutrients") or []

        # --- CENTRALIZED HASH LOGIC ---
        # Now we call the Model to calculate the hash.
        # We pass the dict and list of micros explicitly.
        content_hash = NutritionFacts.generate_hash(
            source=facts_data, micronutrients=micros_data
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
            product=product, nutrition_facts=facts
        )

        # Add flavors
        flavor_names = nutr_data.get("flavor_names")
        if flavor_names:
            for flav_name in flavor_names:
                flavor, _created = Flavor.objects.get_or_create(name=flav_name)
                profile.flavors.add(flavor)
