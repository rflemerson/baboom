"""Mutation definitions for the core GraphQL schema."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import cast

import strawberry
from django.core.exceptions import ValidationError as DjangoValidationError

from baboom.utils import format_graphql_errors
from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.services import (
    AlertSubscriptionService,
    ProductCreateService,
    ProductMetadataUpdateService,
)
from core.types import (
    MicronutrientPayload,
    NutritionFactsPayload,
    ProductCreateInput,
    ProductNutritionPayload,
    ProductStorePayload,
)
from core.types import ProductComponentInput as ProductComponentDTO
from core.types import ProductMetadataUpdateInput as ProductMetadataUpdateDTO

from .types import AlertSubscriptionResult, ProductResult

graphql_inputs = import_module("core.graphql.inputs")
graphql_types = import_module("core.graphql.types")

logger = logging.getLogger(__name__)


@strawberry.type
class CoreMutation:
    """Core mutations."""

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def subscribe_alerts(self, email: str) -> AlertSubscriptionResult:
        """Subscribe an email to price alerts."""
        try:
            result = AlertSubscriptionService().execute(email=email)
            return AlertSubscriptionResult(
                success=not result.already_subscribed,
                already_subscribed=result.already_subscribed,
                email=result.email,
            )
        except DjangoValidationError as e:
            return AlertSubscriptionResult(
                success=False,
                email=email,
                errors=format_graphql_errors(e),
            )

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def create_product(
        self,
        data: graphql_inputs.ProductInput,
    ) -> ProductResult:
        """Create a new product with all related data."""
        stores_data = CoreMutation._map_store_data(data.stores) if data.stores else []
        nutrition_data = (
            CoreMutation._map_nutrition_data(data.nutrition) if data.nutrition else []
        )

        try:
            # Prepare tags from paths if provided, else use legacy
            tags_to_use: list[str] | list[list[str]] | None = None
            if data.tag_paths:
                tags_to_use = [tp.path for tp in data.tag_paths]
            elif data.tags:
                tags_to_use = data.tags

            input_data = ProductCreateInput(
                name=data.name,
                weight=data.weight,
                brand_name=data.brand_name,
                category_name=data.category_path or data.category_name,
                ean=data.ean,
                description=data.description,
                packaging=data.packaging.value,
                is_published=data.is_published,
                tags=tags_to_use,
                stores=stores_data,
                nutrition=nutrition_data,
                origin_scraped_item_id=data.origin_scraped_item_id,
                is_combo=data.is_combo,
                components=[
                    ProductComponentDTO(
                        name=c.name,
                        ean=c.ean,
                        external_id=c.external_id,
                        quantity=c.quantity,
                    )
                    for c in data.components
                ]
                if data.components
                else None,
            )

            product = ProductCreateService().execute(input_data)

            return ProductResult(product=cast("graphql_types.ProductType", product))

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def update_product_content(
        self,
        product_id: int,
        data: graphql_inputs.ProductContentUpdateInput,
    ) -> ProductResult:
        """Update product content (LLM enrichment)."""
        try:
            updated_product = ProductMetadataUpdateService().execute(
                product_id=product_id,
                data=ProductMetadataUpdateDTO(
                    name=data.name,
                    description=data.description,
                    category_name=data.category_path or data.category_name,
                    packaging=data.packaging.value if data.packaging else None,
                    tags=(
                        [tag_path.path for tag_path in data.tag_paths]
                        if data.tag_paths
                        else data.tags
                    ),
                ),
            )
            return ProductResult(
                product=cast("graphql_types.ProductType", updated_product),
            )

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))

    @staticmethod
    def _map_store_data(
        stores: list[graphql_inputs.ProductStoreInput],
    ) -> list[ProductStorePayload]:
        return [
            ProductStorePayload(
                store_name=store_input.store_name,
                product_link=store_input.product_link,
                price=store_input.price,
                external_id=store_input.external_id,
                affiliate_link=store_input.affiliate_link,
                stock_status=store_input.stock_status.value,
            )
            for store_input in stores
        ]

    @staticmethod
    def _map_nutrition_data(
        nutrition: list[graphql_inputs.ProductNutritionInput],
    ) -> list[ProductNutritionPayload]:
        return [
            ProductNutritionPayload(
                flavor_names=nutrition_profile.flavor_names,
                nutrition_facts=NutritionFactsPayload(
                    description=nutrition_profile.nutrition_facts.description,
                    serving_size_grams=(
                        nutrition_profile.nutrition_facts.serving_size_grams
                    ),
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
