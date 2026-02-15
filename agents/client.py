import logging
import os

import requests

logger = logging.getLogger(__name__)


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
        try:
            # Timeout: 10s to connect, 120s to wait for response (LLMs take time)
            response = requests.post(
                self.url,
                json={"query": query, "variables": variables},
                headers=self.headers,
                timeout=(10, 120),
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                # Log error but return data for caller decision
                logger.error(f"GraphQL Error: {data['errors']}")
                raise Exception(f"API Error: {data['errors'][0]['message']}")

            return data
        except Exception as e:
            logger.error(f"Network Error ({self.url}): {e}")
            raise

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
        mutation = """
        mutation($force: Boolean, $targetItemId: Int) {
            checkoutScrapedItem(force: $force, targetItemId: $targetItemId) {
                id
                productLink
                sourcePageUrl
                storeSlug
                storeName
                externalId
                price
                stockStatus
            }
        }
        """
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
        if result and result.get("errors"):
            logger.error(f"Product creation failed: {result['errors']}")
            raise Exception(f"Product creation failed: {result['errors']}")
        return result
