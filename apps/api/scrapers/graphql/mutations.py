"""Mutations for scraper control and item lifecycle operations."""

from __future__ import annotations

import strawberry
from django.core.exceptions import ValidationError as DjangoValidationError

from baboom.utils import format_graphql_errors
from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.dtos import ScrapedItemApprovalInput as ScrapedItemApprovalDTO
from scrapers.services import (
    ScrapedItemApprovalService,
    ScrapedItemCheckoutService,
    ScrapedItemErrorService,
    ScrapedItemExtractionSubmitService,
    ScrapedItemReviewStateService,
    build_agent_extraction_submit_input,
)

from .inputs import (
    AgentExtractionInput,
    ScrapedItemActionInput,
    ScrapedItemApprovalInput,
    ScrapedItemCheckoutInput,
    ScrapedItemErrorInput,
)
from .types import (
    CatalogCandidateType,
    ScrapedItemApprovalResult,
    ScrapedItemExtractionResult,
    ScrapedItemExtractionType,
    ScrapedItemResult,
    ScrapedItemType,
)

_STRAWBERRY_RUNTIME_TYPES = (
    AgentExtractionInput,
    ScrapedItemActionInput,
    ScrapedItemApprovalInput,
    ScrapedItemCheckoutInput,
    ScrapedItemErrorInput,
    ScrapedItemApprovalResult,
    ScrapedItemExtractionResult,
    ScrapedItemExtractionType,
    ScrapedItemResult,
    ScrapedItemType,
)


@strawberry.type
class ScrapersMutation:
    """Mutations for scraper management."""

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def checkout_scraped_item(
        self,
        data: ScrapedItemCheckoutInput | None = None,
    ) -> ScrapedItemType | None:
        """Reserve one scraped item for agent processing."""
        return ScrapedItemCheckoutService().execute(
            item_id=data.item_id if data is not None else None,
        )

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def heartbeat_scraped_item(self, data: ScrapedItemActionInput) -> ScrapedItemResult:
        """Keep an interactive review reservation active."""
        try:
            item = ScrapedItemReviewStateService().heartbeat(item_id=data.item_id)
            return ScrapedItemResult(item=item)
        except DjangoValidationError as exc:
            return ScrapedItemResult(errors=format_graphql_errors(exc))

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def release_scraped_item(self, data: ScrapedItemActionInput) -> ScrapedItemResult:
        """Return an active item to the queue without recording an error."""
        try:
            item = ScrapedItemReviewStateService().release(item_id=data.item_id)
            return ScrapedItemResult(item=item)
        except DjangoValidationError as exc:
            return ScrapedItemResult(errors=format_graphql_errors(exc))

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def ignore_scraped_item(self, data: ScrapedItemActionInput) -> ScrapedItemResult:
        """Mark a review item as intentionally ignored."""
        try:
            item = ScrapedItemReviewStateService().ignore(item_id=data.item_id)
            return ScrapedItemResult(item=item)
        except DjangoValidationError as exc:
            return ScrapedItemResult(errors=format_graphql_errors(exc))

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def report_scraped_item_error(
        self,
        data: ScrapedItemErrorInput,
    ) -> bool:
        """Report an error for a processing scraped item."""
        return ScrapedItemErrorService().execute(
            item_id=data.item_id,
            message=data.message,
            is_fatal=data.is_fatal,
        )

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def submit_agent_extraction(
        self,
        data: AgentExtractionInput,
    ) -> ScrapedItemExtractionResult:
        """Stage the agent extraction payload for review."""
        payload = {
            "origin_scraped_item_id": data.origin_scraped_item_id,
            "source_page_id": data.source_page_id,
            "source_page_url": data.source_page_url,
            "store_slug": data.store_slug,
            "image_report": data.image_report,
            "product": data.product,
        }
        try:
            extraction = ScrapedItemExtractionSubmitService().execute(
                build_agent_extraction_submit_input(payload),
            )
            return ScrapedItemExtractionResult(
                extraction=ScrapedItemExtractionType.from_model(extraction),
            )
        except DjangoValidationError as exc:
            return ScrapedItemExtractionResult(errors=format_graphql_errors(exc))

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def approve_scraped_item(
        self,
        data: ScrapedItemApprovalInput,
    ) -> ScrapedItemApprovalResult:
        """Apply a human-approved staged extraction to the catalog."""
        create_product = data.create_product
        payload = {
            "itemId": data.item_id,
            "productId": data.product_id,
            "createProduct": (
                {
                    "name": create_product.name,
                    "brandId": create_product.brand_id,
                    "weight": create_product.weight,
                    "categoryId": create_product.category_id,
                    "ean": create_product.ean,
                    "description": create_product.description,
                    "packaging": create_product.packaging,
                    "tagIds": create_product.tag_ids,
                    "isPublished": create_product.is_published,
                }
                if create_product is not None
                else None
            ),
        }
        try:
            product = ScrapedItemApprovalService().execute(
                ScrapedItemApprovalDTO.model_validate(payload),
            )
            return ScrapedItemApprovalResult(
                product=CatalogCandidateType.from_model(product),
            )
        except (DjangoValidationError, ValueError) as exc:
            if isinstance(exc, DjangoValidationError):
                error = exc
            else:
                error = DjangoValidationError({"approval": [str(exc)]})
            return ScrapedItemApprovalResult(errors=format_graphql_errors(error))
