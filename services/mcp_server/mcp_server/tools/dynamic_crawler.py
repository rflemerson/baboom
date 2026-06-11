"""Fetch JS-rendered pages with Playwright and extract structured data from the HTML.

Some stores only render product data after the page loads in a browser. Instead
of screenshotting the page, we grab the rendered HTML and turn it into
structured JSON (JSON-LD, meta tags, tables, images). The extraction is
deliberately neutral: it reports everything the page exposes, with enough
metadata (alt text, where each image was referenced) for the agent to decide
what is relevant.
"""

import asyncio
import json
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .preparation import (
    extract_image_urls_from_payload,
    looks_like_image_url,
    normalize_url,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
META_KEYS = ("property", "name", "itemprop")
IMG_SRC_ATTRS = ("src", "data-src", "data-lazy-src", "data-original")


async def fetch_rendered_html_async(
    url: str, timeout_ms: int = 60000, settle_ms: int = 3000, scroll_steps: int = 10
) -> str:
    """Open the URL in headless Chromium and return the rendered HTML."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=USER_AGENT,
            )
            page = await context.new_page()
            await page.goto(url, timeout=timeout_ms, wait_until="load")
            # Allow client-side rendering and anti-bot checks to settle.
            await page.wait_for_timeout(settle_ms)
            # Scroll through the page so lazily rendered sections mount
            # (some stores only render content below the fold on scroll).
            for _ in range(scroll_steps):
                await page.mouse.wheel(0, 2000)
                await page.wait_for_timeout(300)
            await page.wait_for_timeout(1000)
            return await page.content()
        finally:
            await browser.close()


def fetch_rendered_html(
    url: str, timeout_ms: int = 60000, settle_ms: int = 3000, scroll_steps: int = 10
) -> str:
    return asyncio.run(
        fetch_rendered_html_async(url, timeout_ms, settle_ms, scroll_steps)
    )


def _extract_json_ld(soup: BeautifulSoup) -> list[Any]:
    blocks = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        blocks.extend(data if isinstance(data, list) else [data])
    return blocks


def _extract_meta(soup: BeautifulSoup) -> dict[str, str]:
    meta = {}
    for tag in soup.find_all("meta"):
        content = tag.get("content")
        if not content:
            continue
        for attr in META_KEYS:
            key = tag.get(attr)
            if key and key not in meta:
                meta[key] = content
    return meta


def _extract_tables(soup: BeautifulSoup) -> list[list[list[str]]]:
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [
                cell.get_text(separator=" ", strip=True)
                for cell in tr.find_all(["th", "td"])
            ]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def _add_image(
    images: dict[str, dict[str, Any]],
    url: str,
    source: str,
    base_url: str | None,
    alt: str | None = None,
) -> None:
    normalized = normalize_url(url, base_url=base_url)
    entry = images.setdefault(
        normalized, {"url": normalized, "alt": None, "sources": []}
    )
    if source not in entry["sources"]:
        entry["sources"].append(source)
    if alt and not entry["alt"]:
        entry["alt"] = alt


def _extract_images(
    soup: BeautifulSoup,
    meta: dict[str, str],
    json_ld: list[Any],
    base_url: str | None,
) -> list[dict[str, Any]]:
    """Collect every image the page references, in document order, annotated
    with where it came from so the agent can judge relevance."""
    images: dict[str, dict[str, Any]] = {}

    for key, value in meta.items():
        if "image" in key.lower() or looks_like_image_url(value):
            _add_image(images, value, f"meta:{key}", base_url)

    for block in json_ld:
        block_type = block.get("@type") if isinstance(block, dict) else None
        source = f"jsonld:{block_type}" if block_type else "jsonld"
        for url in extract_image_urls_from_payload(block, base_url=base_url):
            _add_image(images, url, source, base_url)

    for img in soup.find_all("img"):
        for attr in IMG_SRC_ATTRS:
            src = img.get(attr)
            if src and not src.startswith("data:"):
                _add_image(images, src, "html:img", base_url, alt=img.get("alt"))

    return list(images.values())


def extract_page_data(html: str, base_url: str | None = None) -> dict[str, Any]:
    """Parse rendered HTML into structured JSON: title, meta, JSON-LD, tables, images."""
    soup = BeautifulSoup(html, "html.parser")
    json_ld = _extract_json_ld(soup)
    meta = _extract_meta(soup)

    return {
        "title": soup.title.get_text(strip=True) if soup.title else None,
        "meta": meta,
        "jsonLd": json_ld,
        "tables": _extract_tables(soup),
        "images": _extract_images(soup, meta, json_ld, base_url),
    }


def fetch_page_data(url: str) -> dict[str, Any]:
    """Fetch a JS-rendered page and return its HTML plus structured data."""
    html = fetch_rendered_html(url)
    return {"html": html, **extract_page_data(html, base_url=url)}
