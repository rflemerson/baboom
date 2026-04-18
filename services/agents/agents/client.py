"""HTTP client used by the agents service to communicate with the backend API."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, NoReturn

import requests

logger = logging.getLogger(__name__)

SCRAPED_ITEM_CHECKOUT_FIELDS = """
id
productLink
sourcePageUrl
sourcePageApiContext
sourcePageHtmlStructuredData
storeSlug
storeName
externalId
price
stockStatus
"""

SCRAPED_ITEM_DETAILS_FIELDS = """
id
name
status
storeSlug
storeName
externalId
price
stockStatus
productLink
sourcePageUrl
sourcePageId
sourcePageApiContext
sourcePageHtmlStructuredData
productStoreId
linkedProductId
"""

SCRAPED_ITEM_MUTATION_FIELDS = """
id
name
status
storeSlug
externalId
sourcePageUrl
sourcePageId
productStoreId
linkedProductId
"""

SCRAPED_ITEM_VARIANT_FIELDS = """
id
name
status
storeSlug
externalId
price
stockStatus
sourcePageUrl
sourcePageId
productStoreId
linkedProductId
"""

GRAPHQL_SELECTION_CLOSE = """
            }
        }
        """


class AgentClientError(RuntimeError):
    """Raised when the backend API returns an invalid or failed response."""


class AgentClient:
    """Pure Python HTTP Client. Knows nothing about Django."""

    def __init__(self) -> None:
        """Read runtime configuration directly from environment variables."""
        self.api_key = os.environ.get("AGENTS_API_KEY", "")
        self.url = os.environ.get("AGENTS_API_URL", "http://localhost:8000/graphql/")

        self.headers = {"Content-Type": "application/json", "X-API-KEY": self.api_key}
        if not self.api_key:
            logger.warning("AGENTS_API_KEY is not defined. Requests may fail.")

    def _send(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        retries = max(1, int(os.environ.get("AGENTS_HTTP_RETRIES", "3")))
        backoff = float(os.environ.get("AGENTS_HTTP_RETRY_BACKOFF", "0.6"))
        last_exception: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    self.url,
                    json={"query": query, "variables": variables},
                    headers=self.headers,
                    timeout=(10, 120),
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    if attempt < retries:
                        time.sleep(backoff * attempt)
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                data = response.json()

                if "errors" in data:
                    self._raise_graphql_error(data["errors"])
                else:
                    return data
            except (requests.RequestException, ValueError, AgentClientError) as exc:
                last_exception = exc
                if attempt < retries:
                    time.sleep(backoff * attempt)
                    continue
                logger.exception("Network error while calling %s", self.url)
                raise

        if last_exception:
            raise last_exception
        self._raise_unexpected_request_flow()
        return {}

    def checkout_work(
        self,
        *,
        force: bool = False,
        target_item_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Checkout a ScrapedItem for processing."""
        mutation = (
            """
        mutation($force: Boolean, $targetItemId: Int) {
            checkoutScrapedItem(force: $force, targetItemId: $targetItemId) {
        """
            + SCRAPED_ITEM_CHECKOUT_FIELDS
            + GRAPHQL_SELECTION_CLOSE
        )
        data = self._send(mutation, {"force": force, "targetItemId": target_item_id})
        return data.get("data", {}).get("checkoutScrapedItem")

    def report_error(
        self,
        item_id: int,
        message: str,
        *,
        is_fatal: bool = False,
    ) -> None:
        """Report a processing error back to the API."""
        mutation = """
        mutation($data: ScrapedItemErrorInput!) {
            reportScrapedItemError(data: $data)
        }
        """
        self._send(
            mutation,
            {
                "data": {
                    "itemId": int(item_id),
                    "message": str(message),
                    "isFatal": is_fatal,
                },
            },
        )

    def create_product(self, product_input: dict[str, Any]) -> dict[str, Any]:
        """Create a new Product via the API."""
        mutation = """
        mutation($data: ProductInput!) {
            createProduct(data: $data) {
                product { id }
                errors { field message }
            }
        }
        """
        data = self._send(mutation, {"data": product_input})
        result = data.get("data", {}).get("createProduct")
        if not result:
            self._raise_empty_create_product_response()
        if result.get("errors"):
            self._raise_create_product_errors(result["errors"])
        product = result.get("product")
        if not product or not product.get("id"):
            self._raise_missing_product_id()
        return result

    def get_scraped_item(self, item_id: int) -> dict[str, Any] | None:
        """Fetch one scraped item snapshot for pipeline state decisions."""
        query = (
            """
        query($itemId: Int!) {
            scrapedItem(itemId: $itemId) {
        """
            + SCRAPED_ITEM_DETAILS_FIELDS
            + GRAPHQL_SELECTION_CLOSE
        )
        data = self._send(query, {"itemId": int(item_id)})
        return data.get("data", {}).get("scrapedItem")

    def ensure_source_page(
        self,
        item_id: int,
        url: str,
        store_slug: str,
    ) -> dict[str, Any] | None:
        """Ensure source page exists and is linked to the scraped item."""
        mutation = (
            """
        mutation($itemId: Int!, $url: String!, $storeSlug: String!) {
            ensureScrapedItemSourcePage(
                itemId: $itemId,
                url: $url,
                storeSlug: $storeSlug
            ) {
        """
            + SCRAPED_ITEM_MUTATION_FIELDS
            + GRAPHQL_SELECTION_CLOSE
        )
        data = self._send(
            mutation,
            {"itemId": int(item_id), "url": str(url), "storeSlug": str(store_slug)},
        )
        return data.get("data", {}).get("ensureScrapedItemSourcePage")

    def update_scraped_item_data(
        self,
        item_id: int,
        name: str | None = None,
        source_page_url: str | None = None,
        store_slug: str | None = None,
    ) -> dict[str, Any] | None:
        """Update mutable scraped item fields used by agents flow."""
        mutation = (
            """
        mutation(
            $itemId: Int!,
            $name: String,
            $sourcePageUrl: String,
            $storeSlug: String
        ) {
            updateScrapedItemData(
                itemId: $itemId,
                name: $name,
                sourcePageUrl: $sourcePageUrl,
                storeSlug: $storeSlug
            ) {
        """
            + SCRAPED_ITEM_MUTATION_FIELDS
            + GRAPHQL_SELECTION_CLOSE
        )
        data = self._send(
            mutation,
            {
                "itemId": int(item_id),
                "name": name,
                "sourcePageUrl": source_page_url,
                "storeSlug": store_slug,
            },
        )
        return data.get("data", {}).get("updateScrapedItemData")

    def upsert_scraped_item_variant(
        self,
        origin_item_id: int,
        external_id: str,
        name: str,
        page_url: str,
        store_slug: str,
        price: float | None = None,
        stock_status: str | None = None,
    ) -> dict[str, Any] | None:
        """Create or update a variant scraped item for multi-product pages."""
        mutation = (
            """
        mutation($data: ScrapedItemVariantInput!) {
            upsertScrapedItemVariant(data: $data) {
            """
            + SCRAPED_ITEM_VARIANT_FIELDS
            + GRAPHQL_SELECTION_CLOSE
        )
        data = self._send(
            mutation,
            {
                "data": {
                    "originItemId": int(origin_item_id),
                    "externalId": str(external_id),
                    "name": str(name),
                    "pageUrl": str(page_url),
                    "storeSlug": str(store_slug),
                    "price": price,
                    "stockStatus": stock_status,
                },
            },
        )
        return data.get("data", {}).get("upsertScrapedItemVariant")

    @staticmethod
    def _raise_graphql_error(errors: object) -> None:
        logger.error("GraphQL error: %s", errors)
        first_error = (
            errors[0]["message"]
            if isinstance(errors, list) and errors
            else "Unknown API error"
        )
        message = f"API Error: {first_error}"
        raise AgentClientError(message)

    @staticmethod
    def _raise_unexpected_request_flow() -> NoReturn:
        message = "Unexpected request flow"
        raise RuntimeError(message)

    @staticmethod
    def _raise_empty_create_product_response() -> None:
        message = "Product creation failed: empty createProduct response"
        raise AgentClientError(message)

    @staticmethod
    def _raise_missing_product_id() -> None:
        message = "Product creation failed: missing product id in response"
        raise AgentClientError(message)

    @staticmethod
    def _raise_create_product_errors(errors: object) -> None:
        logger.error("Product creation failed: %s", errors)
        message = f"Product creation failed: {errors}"
        raise AgentClientError(message)
