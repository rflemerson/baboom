"""Scrapy spider template for Wap.Store catalog APIs."""

from __future__ import annotations

import logging
import os

from scrapy import Request
from scrapy.http import Response

from ..base import CatalogSpider
from ...normalizers.wapstore import WapStoreNormalizer

logger = logging.getLogger(__name__)

PAGE_SIZE = 30
WAPSTORE_SUCCESS_CODE = 200


class WapStoreApiSpider(CatalogSpider):
    """Crawl Wap.Store menu categories and offset-based product listings."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    API_LISTING = ""
    API_MENU = ""
    normalizer = WapStoreNormalizer()
    FALLBACK_CATEGORIES: tuple[str, ...] = ()

    def __init__(self, **kwargs: object) -> None:
        """Read the existing opt-in SSL verification setting."""
        super().__init__(**kwargs)
        self.ssl_verify = os.getenv("GROWTH_SSL_VERIFY", "0") == "1"

    def get_headers(self) -> dict[str, str]:
        """Return the headers required by Wap.Store's JSON API."""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "app-token": "wapstore",
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
            "Sec-Ch-Ua": '"Chromium";v="120", "Google Chrome";v="120", "Not_A Brand";v="8"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _api_meta(self) -> dict[str, object]:
        """Pass the same TLS verification choice to scrapy-impersonate."""
        return {"impersonate_args": {"verify": self.ssl_verify}}

    def category_discovery_request(self) -> Request:
        """Start Wap.Store menu discovery."""
        return self.request(
            self.API_MENU,
            callback=self._parse_menu,
            headers=self.get_headers(),
            meta=self._api_meta(),
        )

    def category_request(self, category: str) -> Request:
        """Request the first Wap.Store offset page for a category."""
        return self.request(
            self.API_LISTING,
            callback=self._parse_category,
            params={"url": category, "offset": 0, "limit": PAGE_SIZE},
            headers=self.get_headers(),
            meta={**self._api_meta(), "category": category, "offset": 0},
        )

    def _parse_menu(self, response: Response):
        """Flatten a menu response and schedule category requests."""
        if response.status != WAPSTORE_SUCCESS_CODE:
            logger.warning("Menu API failed: %s", response.status)
            yield from self.requests_for_categories(self.FALLBACK_CATEGORIES)
            return
        try:
            data = response.json()
            items = data.get("data") or data.get("menu") or []
            paths: set[str] = set()
            self._extract_recursive_category_paths(
                items if isinstance(items, list) else [],
                paths,
            )
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.debug("Wap.Store menu payload parse error: %s", exc)
            paths = set()
        yield from self.requests_for_categories(self.categories_or_fallback(paths))

    def _extract_recursive_category_paths(
        self,
        nodes: list[object],
        paths: set[str],
    ) -> None:
        """Walk nested menu nodes and retain valid product paths."""
        for node in nodes:
            if not isinstance(node, dict):
                continue
            self._add_category_path(node, paths)
            children = node.get("children") or node.get("itens") or []
            if isinstance(children, list):
                self._extract_recursive_category_paths(children, paths)

    def _add_category_path(self, node: dict[str, object], paths: set[str]) -> None:
        """Normalize one menu link to a relative category path."""
        url = node.get("url") or node.get("link")
        if not url:
            return
        path = str(url).replace(self.BASE_URL, "")
        if not path.startswith("/"):
            path = f"/{path}"
        if not path.endswith("/"):
            path = f"{path}/"
        if len(path) > 1 and self._is_valid_category_path(path):
            paths.add(path)

    def _parse_category(self, response: Response):
        """Normalize one Wap.Store page and continue offset pagination."""
        category = str(response.meta["category"])
        offset = int(response.meta["offset"])
        if response.status != WAPSTORE_SUCCESS_CODE:
            logger.warning("Failed category %s at offset %s: %s", category, offset, response.status)
            return
        try:
            data = response.json()
            products = self._extract_products_list(data if isinstance(data, dict) else {})
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.debug("Wap.Store item page parse error for %s: %s", category, exc)
            products = []
        yield from self.emit_products(products, category)
        if len(products) >= PAGE_SIZE:
            next_offset = offset + PAGE_SIZE
            yield self.request(
                response.url.split("?", maxsplit=1)[0],
                callback=self._parse_category,
                params={"url": category, "offset": next_offset, "limit": PAGE_SIZE},
                headers=self.get_headers(),
                meta={**self._api_meta(), "category": category, "offset": next_offset},
                dont_filter=True,
            )

    def _extract_products_list(self, data: dict[str, object]) -> list[dict[str, object]]:
        """Support both Wap.Store response envelopes."""
        content = data.get("conteudo")
        if isinstance(content, dict) and isinstance(content.get("produtos"), list):
            return content["produtos"]
        data_node = data.get("data")
        if isinstance(data_node, dict) and isinstance(data_node.get("list"), list):
            return data_node["list"]
        return []

    def is_valid_category_path(self, path: str) -> bool:
        """Return whether a menu path is a product category."""
        return self._is_valid_category_path(path)

    def _is_valid_category_path(self, path: str) -> bool:
        """Filter account, checkout, editorial, and policy routes."""
        invalid_tokens = {
            "conta",
            "carrinho",
            "checkout",
            "institucional",
            "blog",
            "atendimento",
            "politica",
            "privacidade",
            "termos",
        }
        lowered = path.lower()
        return not any(token in lowered for token in invalid_tokens)
