"""Opt-in browser integration coverage against a real Growth page."""

from __future__ import annotations

import asyncio
import os
from unittest import skipUnless

from mcp_server.tools.browser import BrowserManager


@skipUnless(
    os.getenv("RUN_EXTERNAL_SCRAPER_TESTS") == "1"
    and bool(os.getenv("GROWTH_SCRAPED_PAGE_ID")),
    "set RUN_EXTERNAL_SCRAPER_TESTS=1 and GROWTH_SCRAPED_PAGE_ID",
)
def test_growth_browser_captures_json_network_response() -> None:
    """A real browser can observe JSON fetched by the Growth application."""
    asyncio.run(_capture_growth_response())


async def _capture_growth_response() -> None:
    """Open the configured Growth page and inspect its JSON requests."""
    manager = BrowserManager()
    page_id = int(os.environ["GROWTH_SCRAPED_PAGE_ID"])
    try:
        await manager.open_page(page_id)
        result = await manager.network("api")
        assert result["count"] >= 1
    finally:
        await manager.close()
