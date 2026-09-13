"""Scrapy spider template for VTEX persisted GraphQL search."""

from __future__ import annotations

import base64
import json
import logging
from typing import TYPE_CHECKING

from ...normalizers.vtex import VtexNormalizer
from ..base import CatalogSpider

if TYPE_CHECKING:
    from collections.abc import Iterator

    from scrapy import Request
    from scrapy.http import Response

    from ...contracts import ScrapedProductInput


logger = logging.getLogger(__name__)

PAGE_SIZE = 50
VTEX_GRAPHQL_SUCCESS_CODE = 200


class VtexGraphqlSpider(CatalogSpider):
    """Crawl VTEX GraphQL category ranges and emit normalized pages."""

    BRAND_NAME = ""
    STORE_SLUG = ""
    BASE_URL = ""
    API_ENDPOINT = ""
    API_TREE = ""
    QUERY_HASH = ""
    normalizer = VtexNormalizer(context_platform="vtex_graphql")
    FALLBACK_CATEGORIES: tuple[str, ...] = ()

    def category_discovery_request(self) -> Request:
        """Start the GraphQL store's category discovery request."""
        return self.request(
            self.API_TREE,
            callback=self._parse_categories,
            headers=self.get_headers(),
        )

    def category_request(self, category: str) -> Request:
        """Request the first persisted GraphQL range for a category."""
        return self.request(
            self.API_ENDPOINT,
            callback=self._parse_category,
            params=self._build_graphql_params(category, 0, PAGE_SIZE - 1),
            headers=self.get_headers(),
            meta={"category": category, "start": 0},
        )

    def get_headers(self) -> dict[str, str]:
        """Return headers accepted by the VTEX GraphQL endpoint."""
        return {"Accept": "application/json"}

    def _parse_categories(
        self,
        response: Response,
    ) -> Iterator[Request | ScrapedProductInput]:
        """Extract category slugs and schedule category requests."""
        try:
            payload = response.json()
            categories = payload if isinstance(payload, list) else []
            slugs = {
                str(item.get("url", "")).rstrip("/").split("/")[-1]
                for item in categories
                if isinstance(item, dict) and item.get("url")
            }
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.debug("VTEX GraphQL category payload parse error: %s", exc)
            slugs = set()
        yield from self.requests_for_categories(self.categories_or_fallback(slugs))

    def _parse_category(
        self,
        response: Response,
    ) -> Iterator[Request | ScrapedProductInput]:
        """Normalize one GraphQL range and continue while it is full."""
        category = str(response.meta["category"])
        start = int(response.meta["start"])
        try:
            data = response.json()
            items = self._parse_graphql_response(data if isinstance(data, dict) else {})
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.debug("VTEX GraphQL item page parse error for %s: %s", category, exc)
            items = []
        yield from self.emit_products(items, category)
        if len(items) >= PAGE_SIZE:
            next_start = start + PAGE_SIZE
            yield self.request(
                response.url.split("?", maxsplit=1)[0],
                callback=self._parse_category,
                params=self._build_graphql_params(
                    category, next_start, next_start + PAGE_SIZE - 1
                ),
                headers=self.get_headers(),
                meta={"category": category, "start": next_start},
            )

    def _build_variables_payload(
        self, category: str, start: int, end: int
    ) -> dict[str, object]:
        """Build the variables object used by VTEX's persisted query."""
        return {
            "hideUnavailableItems": False,
            "category": category,
            "specificationFilters": [],
            "orderBy": "OrderByScoreDESC",
            "from": start,
            "to": end,
            "shippingOptions": [],
            "variant": "",
            "advertisementOptions": {
                "showSponsored": False,
                "sponsoredCount": 0,
                "repeatSponsoredProducts": False,
                "advertisementPlacement": "home_shelf",
            },
        }

    def _build_graphql_params(
        self, category: str, start: int, end: int
    ) -> dict[str, str]:
        """Build the persisted-query URL parameters."""
        variables = json.dumps(
            self._build_variables_payload(category, start, end),
            separators=(",", ":"),
        )
        extensions = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": self.QUERY_HASH,
                "sender": "vtex.store-resources@0.x",
                "provider": "vtex.search-graphql@0.x",
            },
            "variables": base64.b64encode(variables.encode()).decode(),
        }
        return {
            "workspace": "master",
            "maxAge": "short",
            "appsEtag": "remove",
            "domain": "store",
            "locale": "pt-BR",
            "operationName": "Products",
            "variables": "{}",
            "extensions": json.dumps(extensions, separators=(",", ":")),
        }

    def _parse_graphql_response(
        self, data: dict[str, object]
    ) -> list[dict[str, object]]:
        """Extract products from either supported GraphQL response shape."""
        data_node = data.get("data")
        if not isinstance(data_node, dict):
            return []
        search = data_node.get("productSearch")
        if isinstance(search, dict) and isinstance(search.get("products"), list):
            return search["products"]
        direct = data_node.get("products")
        if isinstance(direct, list):
            return direct
        if isinstance(direct, dict) and isinstance(direct.get("products"), list):
            return direct["products"]
        return []
