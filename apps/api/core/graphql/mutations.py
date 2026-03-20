"""Mutation definitions for the core GraphQL schema."""

from __future__ import annotations

import logging

import strawberry
from django.core.exceptions import ValidationError as DjangoValidationError

from baboom.utils import format_graphql_errors
from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.services import (
    AlertSubscriptionService,
    ProductCreateService,
    ProductMetadataUpdateService,
)

from .inputs import ProductContentUpdateInput, ProductInput
from .mappers import build_product_create_input, build_product_metadata_update_input
from .types import AlertSubscriptionResult, ProductResult

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
        data: ProductInput,
    ) -> ProductResult:
        """Create a new product with all related data."""
        try:
            product = ProductCreateService().execute(build_product_create_input(data))
            return ProductResult(product=product)

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def update_product_content(
        self,
        product_id: int,
        data: ProductContentUpdateInput,
    ) -> ProductResult:
        """Update product content (LLM enrichment)."""
        try:
            updated_product = ProductMetadataUpdateService().execute(
                product_id=product_id,
                data=build_product_metadata_update_input(data),
            )
            return ProductResult(product=updated_product)

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))
