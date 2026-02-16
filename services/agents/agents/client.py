"""HTTP client used by the agents service to communicate with the backend API."""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

SCRAPED_ITEM_CHECKOUT_FIELDS = """
id
productLink
sourcePageUrl
sourcePageRawContent
sourcePageContentType
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
sourcePageRawContent
sourcePageContentType
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


class AgentClient:
    """Pure Python HTTP Client. Knows nothing about Django."""

    def __init__(self):
        # Read settings directly from OS Environment
        # Doing this in __init__ ensures we capture env vars set after import (e.g. by dotenv)
        self.api_key = os.environ.get("AGENTS_API_KEY", "")
        self.url = os.environ.get("AGENTS_API_URL", "http://localhost:8000/graphql/")

        self.headers = {"Content-Type": "application/json", "X-API-KEY": self.api_key}
        # Basic configuration validation
        if not self.api_key:
            logger.warning("AGENTS_API_KEY is not defined. Requests may fail.")

    def _send(self, query, variables=None):
        retries = max(1, int(os.environ.get("AGENTS_HTTP_RETRIES", "3")))
        backoff = float(os.environ.get("AGENTS_HTTP_RETRY_BACKOFF", "0.6"))
        last_exception: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                # Timeout: 10s to connect, 120s to wait for response (LLMs take time)
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
                    logger.error(f"GraphQL Error: {data['errors']}")
                    raise Exception(f"API Error: {data['errors'][0]['message']}")

                return data
            except Exception as e:
                last_exception = e
                if attempt < retries:
                    time.sleep(backoff * attempt)
                    continue
                logger.error(f"Network Error ({self.url}): {e}")
                raise

        # Defensive fallback, should never happen due raise above.
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected request flow")

    def ping(self):
        """Check API connectivity."""
        query = "query { __typename }"
        return self._send(query)

    def get_taxonomy(self):
        """Fetch categories and tags from the API."""
        query = """
        query {
            categories { name }
            tags { name }
        }
        """
        data = self._send(query)
        result = data.get("data", {})
        categories = [c["name"] for c in result.get("categories", [])]
        tags = [t["name"] for t in result.get("tags", [])]
        return categories, tags

    def checkout_work(self, force: bool = False, target_item_id: int | None = None):
        """Checkout a ScrapedItem for processing."""
        mutation = (
            """
        mutation($force: Boolean, $targetItemId: Int) {
            checkoutScrapedItem(force: $force, targetItemId: $targetItemId) {
        """
            + SCRAPED_ITEM_CHECKOUT_FIELDS
            + """
            }
        }
        """
        )
        data = self._send(mutation, {"force": force, "targetItemId": target_item_id})
        return data.get("data", {}).get("checkoutScrapedItem")

    def report_error(self, item_id, message, is_fatal=False):
        """Report a processing error back to the API."""
        mutation = """
        mutation($itemId: Int!, $message: String!, $isFatal: Boolean!) {
            reportScrapedItemError(itemId: $itemId, message: $message, isFatal: $isFatal)
        }
        """
        self._send(
            mutation,
            {"itemId": int(item_id), "message": str(message), "isFatal": is_fatal},
        )

    def discard_item(self, item_id, reason):
        """Mark an item as discarded."""
        mutation = """
        mutation($itemId: Int!, $reason: String!) {
            discardScrapedItem(itemId: $itemId, reason: $reason)
        }
        """
        self._send(mutation, {"itemId": int(item_id), "reason": reason})

    def create_product(self, product_input):
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
            raise Exception("Product creation failed: empty createProduct response")
        if result and result.get("errors"):
            logger.error(f"Product creation failed: {result['errors']}")
            raise Exception(f"Product creation failed: {result['errors']}")
        product = result.get("product")
        if not product or not product.get("id"):
            raise Exception("Product creation failed: missing product id in response")
        return result

    def get_scraped_item(self, item_id: int):
        """Fetch one scraped item snapshot for pipeline state decisions."""
        query = (
            """
        query($itemId: Int!) {
            scrapedItem(itemId: $itemId) {
        """
            + SCRAPED_ITEM_DETAILS_FIELDS
            + """
            }
        }
        """
        )
        data = self._send(query, {"itemId": int(item_id)})
        return data.get("data", {}).get("scrapedItem")

    def ensure_source_page(self, item_id: int, url: str, store_slug: str):
        """Ensure source page exists and is linked to the scraped item."""
        mutation = (
            """
        mutation($itemId: Int!, $url: String!, $storeSlug: String!) {
            ensureScrapedItemSourcePage(itemId: $itemId, url: $url, storeSlug: $storeSlug) {
        """
            + SCRAPED_ITEM_MUTATION_FIELDS
            + """
            }
        }
        """
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
    ):
        """Update mutable scraped item fields used by agents flow."""
        mutation = (
            """
        mutation($itemId: Int!, $name: String, $sourcePageUrl: String, $storeSlug: String) {
            updateScrapedItemData(itemId: $itemId, name: $name, sourcePageUrl: $sourcePageUrl, storeSlug: $storeSlug) {
        """
            + SCRAPED_ITEM_MUTATION_FIELDS
            + """
            }
        }
        """
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
    ):
        """Create or update a variant scraped item for multi-product pages."""
        mutation = (
            """
        mutation(
            $originItemId: Int!,
            $externalId: String!,
            $name: String!,
            $pageUrl: String!,
            $storeSlug: String!,
            $price: Float,
            $stockStatus: String
        ) {
            upsertScrapedItemVariant(
                originItemId: $originItemId,
                externalId: $externalId,
                name: $name,
                pageUrl: $pageUrl,
                storeSlug: $storeSlug,
                price: $price,
                stockStatus: $stockStatus
            ) {
            """
            + SCRAPED_ITEM_VARIANT_FIELDS
            + """
            }
        }
        """
        )
        data = self._send(
            mutation,
            {
                "originItemId": int(origin_item_id),
                "externalId": str(external_id),
                "name": str(name),
                "pageUrl": str(page_url),
                "storeSlug": str(store_slug),
                "price": price,
                "stockStatus": stock_status,
            },
        )
        return data.get("data", {}).get("upsertScrapedItemVariant")
