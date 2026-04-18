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
        self.retries = max(1, int(os.environ.get("AGENTS_HTTP_RETRIES", "3")))
        self.retry_backoff = float(os.environ.get("AGENTS_HTTP_RETRY_BACKOFF", "0.6"))

        self.headers = {"Content-Type": "application/json", "X-API-KEY": self.api_key}
        if not self.api_key:
            logger.warning("AGENTS_API_KEY is not defined. Requests may fail.")

    def _send(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_exception: Exception | None = None

        for attempt in range(1, self.retries + 1):
            try:
                response = requests.post(
                    self.url,
                    json={"query": query, "variables": variables},
                    headers=self.headers,
                    timeout=(10, 120),
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    if attempt < self.retries:
                        time.sleep(self.retry_backoff * attempt)
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
                if attempt < self.retries:
                    time.sleep(self.retry_backoff * attempt)
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
        mutation($data: ScrapedItemCheckoutInput!) {
            checkoutScrapedItem(data: $data) {
        """
            + SCRAPED_ITEM_CHECKOUT_FIELDS
            + GRAPHQL_SELECTION_CLOSE
        )
        data = self._send(
            mutation,
            {"data": {"force": force, "targetItemId": target_item_id}},
        )
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

    def submit_extraction(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist the final extraction payload for backend review."""
        mutation = """
        mutation($data: AgentExtractionInput!) {
            submitAgentExtraction(data: $data) {
                extraction {
                    id
                    scrapedItemId
                    sourcePageId
                }
                errors {
                    field
                    message
                }
            }
        }
        """
        data = self._send(mutation, {"data": payload})
        result = data.get("data", {}).get("submitAgentExtraction") or {}
        errors = result.get("errors")
        if errors:
            message = f"Extraction submit failed: {errors}"
            raise AgentClientError(message)
        extraction = result.get("extraction")
        if not extraction:
            message = "Extraction submit failed without errors"
            raise AgentClientError(message)
        return extraction

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
