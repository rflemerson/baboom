"""Dagster adapter for the downstream API publishing stage."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from dagster import AssetExecutionContext, asset

from ...publishing.service import (
    build_publish_origin_context,
    build_upload_metadata,
    publish_analysis_item,
    resolve_analysis_items,
)

if TYPE_CHECKING:
    from ...schemas.product import RawScrapedData
    from ..config import ItemConfig
    from ..resources import AgentClientResource


@asset
def upload_to_api(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    product_analysis: dict,
    scraped_metadata: RawScrapedData,
) -> list[dict]:
    """Create one product per analyzed item and link generated scraped items."""
    api = client.get_client()
    try:
        started = time.perf_counter()
        origin_context = build_publish_origin_context(
            api,
            item_id=config.item_id,
            url=config.url,
            store_slug=config.store_slug,
        )
        items = resolve_analysis_items(
            product_analysis,
            scraped_metadata,
            origin_context.item,
        )

        results: list[dict] = []
        created_count = 0
        for idx, analysis_data in enumerate(items):
            item_result = publish_analysis_item(
                context=context,
                api=api,
                idx=idx,
                analysis_data=analysis_data,
                scraped_metadata=scraped_metadata,
                origin=origin_context,
            )
            if item_result.variant_created:
                created_count += 1
            results.append(item_result.result)

        context.add_output_metadata(
            build_upload_metadata(
                results=results,
                created_count=created_count,
                page_id=origin_context.page_id,
                started=started,
            ),
        )
    except Exception as exc:
        context.log.exception("Upload failed")
        api.report_error(config.item_id, str(exc), is_fatal=False)
        raise
    else:
        return results
