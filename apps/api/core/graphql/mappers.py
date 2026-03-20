"""Boundary mappers from GraphQL inputs to core service DTOs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.dtos import ComboComponentInput as ProductComponentDTO
from core.dtos import (
    MicronutrientPayload,
    NutritionFactsPayload,
    ProductCreateInput,
    ProductNutritionPayload,
    StoreListingPayload,
)
from core.dtos import ProductMetadataUpdateInput as ProductMetadataUpdateDTO

if TYPE_CHECKING:
    from .inputs import (
        ProductContentUpdateInput,
        ProductInput,
        ProductNutritionInput,
    )


def build_product_create_input(data: ProductInput) -> ProductCreateInput:
    """Map GraphQL product creation input to the service DTO."""
    tags_to_use: list[str] | list[list[str]] | None = None
    if data.tag_paths:
        tags_to_use = [tag_path.path for tag_path in data.tag_paths]
    elif data.tags:
        tags_to_use = data.tags

    return ProductCreateInput(
        name=data.name,
        weight=data.weight,
        brand_name=data.brand_name,
        category_name=data.category_path or data.category_name,
        ean=data.ean,
        description=data.description,
        packaging=data.packaging.value,
        is_published=data.is_published,
        tags=tags_to_use,
        stores=map_store_data(data.stores) if data.stores else [],
        nutrition=map_nutrition_data(data.nutrition) if data.nutrition else [],
        is_combo=data.is_combo,
        components=[
            ProductComponentDTO(
                name=component.name,
                ean=component.ean,
                external_id=component.external_id,
                quantity=component.quantity,
            )
            for component in data.components
        ]
        if data.components
        else None,
    )


def build_product_metadata_update_input(
    data: ProductContentUpdateInput,
) -> ProductMetadataUpdateDTO:
    """Map GraphQL metadata update input to the service DTO."""
    return ProductMetadataUpdateDTO(
        name=data.name,
        description=data.description,
        category_name=data.category_path or data.category_name,
        packaging=data.packaging.value if data.packaging else None,
        tags=[tag_path.path for tag_path in data.tag_paths]
        if data.tag_paths
        else data.tags,
    )


def map_store_data(stores: list) -> list[StoreListingPayload]:
    """Map GraphQL store input rows to store listing DTOs."""
    return [
        StoreListingPayload(
            store_name=store_input.store_name,
            product_link=store_input.product_link,
            price=store_input.price,
            external_id=store_input.external_id,
            affiliate_link=store_input.affiliate_link,
            stock_status=store_input.stock_status.value,
        )
        for store_input in stores
    ]


def map_nutrition_data(
    nutrition: list[ProductNutritionInput],
) -> list[ProductNutritionPayload]:
    """Map GraphQL nutrition input rows to product nutrition DTOs."""
    return [
        ProductNutritionPayload(
            flavor_names=nutrition_profile.flavor_names,
            nutrition_facts=NutritionFactsPayload(
                description=nutrition_profile.nutrition_facts.description,
                serving_size_grams=nutrition_profile.nutrition_facts.serving_size_grams,
                energy_kcal=nutrition_profile.nutrition_facts.energy_kcal,
                proteins=nutrition_profile.nutrition_facts.proteins,
                carbohydrates=nutrition_profile.nutrition_facts.carbohydrates,
                total_sugars=nutrition_profile.nutrition_facts.total_sugars,
                added_sugars=nutrition_profile.nutrition_facts.added_sugars,
                total_fats=nutrition_profile.nutrition_facts.total_fats,
                saturated_fats=nutrition_profile.nutrition_facts.saturated_fats,
                trans_fats=nutrition_profile.nutrition_facts.trans_fats,
                dietary_fiber=nutrition_profile.nutrition_facts.dietary_fiber,
                sodium=nutrition_profile.nutrition_facts.sodium,
                micronutrients=[
                    MicronutrientPayload(
                        name=micronutrient.name,
                        value=micronutrient.value,
                        unit=micronutrient.unit,
                    )
                    for micronutrient in (
                        nutrition_profile.nutrition_facts.micronutrients or []
                    )
                ],
            ),
        )
        for nutrition_profile in nutrition
    ]
