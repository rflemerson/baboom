"""Mutations for scraper control and item lifecycle operations."""

from __future__ import annotations

import strawberry
from django.core.exceptions import ValidationError as DjangoValidationError

from baboom.utils import format_graphql_errors
from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.services import (
    ScrapedItemCheckoutService,
    ScrapedItemErrorService,
    ScrapedItemExtractionSubmitService,
    ScrapedItemLinkService,
    build_agent_extraction_submit_input,
)

from .inputs import (
    AgentExtractionInput,
    ScrapedItemCheckoutInput,
    ScrapedItemErrorInput,
    ScrapedItemLinkInput,
)
from .types import (
    ScrapedItemExtractionResult,
    ScrapedItemExtractionType,
    ScrapedItemType,
)

_STRAWBERRY_RUNTIME_TYPES = (
    AgentExtractionInput,
    ScrapedItemCheckoutInput,
    ScrapedItemErrorInput,
    ScrapedItemLinkInput,
    ScrapedItemExtractionResult,
    ScrapedItemExtractionType,
    ScrapedItemType,
)


@strawberry.type
class ScrapersMutation:
    """Mutations for scraper management."""

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def checkout_scraped_item(
        self,
        data: ScrapedItemCheckoutInput,
    ) -> ScrapedItemType | None:
        """Reserve one scraped item for agent processing."""
        return ScrapedItemCheckoutService().execute(data)

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def report_scraped_item_error(
        self,
        data: ScrapedItemErrorInput,
    ) -> bool:
        """Report an error for a scraped item."""
        return ScrapedItemErrorService().execute(
            item_id=data.item_id,
            message=data.message,
            is_fatal=data.is_fatal,
        )

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def link_scraped_item_to_product_store(
        self,
        data: ScrapedItemLinkInput,
    ) -> ScrapedItemType | None:
        """Explicitly link a scraped item to a chosen product store."""
        return ScrapedItemLinkService().execute(
            scraped_item_id=data.item_id,
            product_store_id=data.product_store_id,
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
