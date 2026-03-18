"""Mutation definitions for the core GraphQL schema."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any, cast

import strawberry
from django.core.exceptions import ValidationError as DjangoValidationError

from baboom.utils import ValidationError as GqlValidationError
from baboom.utils import format_graphql_errors
from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.models import AlertSubscriber, Product, ProductStore
from core.services import (
    alert_subscriber_create,
    product_create,
    product_update_content,
)
from core.types import ProductComponentInput as ProductComponentDTO
from core.types import ProductCreateInput
from scrapers.models import ScrapedItem
from scrapers.services import ScraperService

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
        if AlertSubscriber.objects.filter(email=email).exists():
            return AlertSubscriptionResult(
                success=False,
                already_subscribed=True,
                email=email,
            )

        try:
            subscriber = alert_subscriber_create(email=email)
            return AlertSubscriptionResult(
                success=True,
                email=subscriber.email,
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
                is_combo=data.is_combo,
                components=[
                    ProductComponentDTO(
                        name=c.name,
                        quantity=c.quantity,
                        weight_hint=c.weight_hint,
                        packaging_hint=c.packaging_hint,
                    )
                    for c in data.components
                ]
                if data.components
                else None,
                nutrient_claims=data.nutrient_claims,
            )

            product = product_create(data=input_data)

            if data.origin_scraped_item_id:
                try:
                    item = ScrapedItem.objects.get(id=data.origin_scraped_item_id)

                    linked_store = ProductStore.objects.filter(
                        product=product,
                        product_link=item.source_page.url if item.source_page else "",
                    ).first()

                    if not linked_store:
                        linked_store = ProductStore.objects.filter(
                            product=product,
                        ).first()

                    if linked_store:
                        item.product_store = linked_store
                        item.status = ScrapedItem.Status.LINKED
                        item.save()

                        # Sync initial price and stock from ScrapedItem to PriceHistory.
                        ScraperService.sync_price_to_core(item)

                except ScrapedItem.DoesNotExist:
                    pass

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
        product = Product.objects.filter(id=product_id).first()
        if not product:
            return ProductResult(
                errors=[
                    GqlValidationError(field="product_id", message="Product not found"),
                ],
            )

        try:
            updated_product = product_update_content(
                product=product,
                name=data.name,
                description=data.description,
                category_name=data.category_name,
                packaging=data.packaging.value if data.packaging else None,
                tags=data.tags,
            )
            return ProductResult(
                product=cast("graphql_types.ProductType", updated_product),
            )

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))

    @staticmethod
    def _map_store_data(
        stores: list[graphql_inputs.ProductStoreInput],
    ) -> list[dict[str, Any]]:
        return [
            {
                "store_name": s.store_name,
                "product_link": s.product_link,
                "price": s.price,
                "external_id": s.external_id,
                "affiliate_link": s.affiliate_link,
                "stock_status": s.stock_status.value,
            }
            for s in stores
        ]

    @staticmethod
    def _map_nutrition_data(
        nutrition: list[graphql_inputs.ProductNutritionInput],
    ) -> list[dict[str, Any]]:
        result = []
        for n in nutrition:
            facts = n.nutrition_facts
            micronutrients_data = []
            if facts.micronutrients:
                micronutrients_data.extend(
                    {"name": m.name, "value": m.value, "unit": m.unit}
                    for m in facts.micronutrients
                )

            result.append(
                {
                    "flavor_names": n.flavor_names,
                    "nutrition_facts": {
                        "description": facts.description,
                        "serving_size_grams": facts.serving_size_grams,
                        "energy_kcal": facts.energy_kcal,
                        "proteins": facts.proteins,
                        "carbohydrates": facts.carbohydrates,
                        "total_sugars": facts.total_sugars,
                        "added_sugars": facts.added_sugars,
                        "total_fats": facts.total_fats,
                        "saturated_fats": facts.saturated_fats,
                        "trans_fats": facts.trans_fats,
                        "dietary_fiber": facts.dietary_fiber,
                        "sodium": facts.sodium,
                        "micronutrients": micronutrients_data,
                    },
                },
            )
        return result
