"""GraphQL transport helpers for the extraction-review backend."""

import os
from typing import Any

import requests


class APIError(RuntimeError):
    """Raised when the backend cannot serve a review request."""


BACKEND_GRAPHQL_URL_MISSING = "BACKEND_GRAPHQL_URL is not configured."
BACKEND_API_KEY_MISSING = "BACKEND_API_KEY is not configured."
INVALID_GRAPHQL_RESPONSE = "Invalid GraphQL response."
MISSING_GRAPHQL_DATA = "GraphQL response has no data."
UNKNOWN_REVIEW_ACTION = "Unknown review action."
UNKNOWN_CATALOG_REFERENCE = "Unknown catalog reference."
MISSING_APPROVAL_PRODUCT = "Approval did not return a product."
MISSING_EXTRACTION_PRODUCT = "Applying the extraction did not return a product."


def _graphql_url() -> str:
    url = os.getenv("BACKEND_GRAPHQL_URL")
    if not url:
        raise APIError(BACKEND_GRAPHQL_URL_MISSING)
    return url


def _headers() -> dict[str, str]:
    api_key = os.getenv("BACKEND_API_KEY")
    if not api_key:
        raise APIError(BACKEND_API_KEY_MISSING)
    return {
        "Content-Type": "application/json",
        "X-API-KEY": api_key,
    }


def graphql_request(
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a GraphQL request and return its data object."""
    response = requests.post(
        _graphql_url(),
        json={"query": query, "variables": variables or {}},
        headers=_headers(),
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, dict):
        raise APIError(INVALID_GRAPHQL_RESPONSE)
    if payload.get("errors"):
        raise APIError(str(payload["errors"]))
    if not isinstance(payload.get("data"), dict):
        raise APIError(MISSING_GRAPHQL_DATA)
    return payload["data"]


ITEM_FIELDS = """
        id
        status
        storeSlug
        storeName
        externalId
        name
        price
        stockStatus
        productLink
        sourcePageUrl
        sourcePageId
        sourcePageContext
        sourcePageStructuredData
        imageUrls
        ean
        category
        lastAttemptAt
        updatedAt
"""


def checkout_scraped_item(item_id: int | None = None) -> dict[str, Any] | None:
    """Reserve the requested queued item, or the next available item."""
    query = (
        "mutation($data: ScrapedItemCheckoutInput) { checkoutScrapedItem(data: $data) {"
        + ITEM_FIELDS
        + "} }"
    )
    data = graphql_request(query, {"data": {"itemId": item_id}})
    return data.get("checkoutScrapedItem")


def review_queue(status: str = "queued", search: str = "", limit: int = 20) -> list:
    """Discover review items without reserving them; filter by status or text."""
    query = (
        "query($status: String, $search: String!, $limit: Int!) { "
        "reviewQueue(status: $status, search: $search, limit: $limit) {"
        + ITEM_FIELDS
        + "} }"
    )
    return graphql_request(query, {"status": status, "search": search, "limit": limit})[
        "reviewQueue"
    ]


def review_item(item_id: int) -> dict:
    """Load one review item together with its staged extraction."""
    query = (
        "query($itemId: Int!) { reviewItem(itemId: $itemId) {"
        + ITEM_FIELDS
        + "} reviewExtraction(itemId: $itemId) { extractedProduct imageReport } }"
    )
    return graphql_request(query, {"itemId": item_id})


def review_action(action: str, item_id: int) -> dict:
    """Apply a heartbeat, release, or ignore action to a review item."""
    if action not in {"heartbeat", "release", "ignore"}:
        raise ValueError(UNKNOWN_REVIEW_ACTION)
    field = f"{action}ScrapedItem"
    query = (
        "mutation($data: ScrapedItemActionInput!) { "
        + field
        + "(data: $data) { item {"
        + ITEM_FIELDS
        + "} errors { field message } } }"
    )
    result = graphql_request(query, {"data": {"itemId": item_id}})[field]
    if result.get("errors"):
        raise APIError(str(result["errors"]))
    return result["item"]


def catalog_candidates(search: str = "", ean: str = "", limit: int = 20) -> list:
    """Search published and unpublished products before proposing creation."""
    query = """
    query($search: String!, $ean: String!, $limit: Int!) {
      catalogCandidates(search: $search, ean: $ean, limit: $limit) {
        id name brandId brandName categoryId categoryName ean netMass massUnit
        packaging isPublished
      }
    }
    """
    return graphql_request(query, {"search": search, "ean": ean, "limit": limit})[
        "catalogCandidates"
    ]


def catalog_choices(kind: str, search: str = "", limit: int = 50) -> list:
    """List IDs for brands, categories or tags accepted by catalog approval."""
    fields = {
        "brands": "catalogBrands",
        "categories": "catalogCategories",
        "tags": "catalogTags",
    }
    if kind not in fields:
        raise ValueError(UNKNOWN_CATALOG_REFERENCE)
    field = fields[kind]
    query = (
        "query($search: String!, $limit: Int!) { "
        + field
        + "(search: $search, limit: $limit) { id name } }"
    )
    return graphql_request(query, {"search": search, "limit": limit})[field]


def approve_scraped_item(payload: dict) -> dict:
    """Create or link a catalog product from an approved review payload."""
    query = """
    mutation($data: ScrapedItemApprovalInput!) {
      approveScrapedItem(data: $data) {
        product {
          id name brandId brandName categoryId categoryName ean netMass massUnit
          packaging isPublished
        }
        errors { field message }
      }
    }
    """
    result = graphql_request(query, {"data": payload})["approveScrapedItem"]
    if result.get("errors"):
        raise APIError(str(result["errors"]))
    if not result.get("product"):
        raise APIError(MISSING_APPROVAL_PRODUCT)
    return result["product"]


def apply_scraped_item_extraction(payload: dict) -> dict:
    """Complete an already linked product using the server's staged extraction."""
    query = """
    mutation($data: ScrapedItemExtractionApplyInput!) {
      applyScrapedItemExtraction(data: $data) {
        product { id name isPublished }
        errors { field message }
      }
    }
    """
    result = graphql_request(query, {"data": payload})["applyScrapedItemExtraction"]
    if result.get("errors"):
        raise APIError(str(result["errors"]))
    if not result.get("product"):
        raise APIError(MISSING_EXTRACTION_PRODUCT)
    return result["product"]


def submit_agent_extraction(data: dict[str, Any]) -> dict[str, Any]:
    """Submit an extraction payload to the backend review staging area."""
    query = """
    mutation SubmitAgentExtraction($data: AgentExtractionInput!) {
      submitAgentExtraction(data: $data) {
        extraction {
          id
        }
        errors {
          field
          message
        }
      }
    }
    """

    result = graphql_request(query, {"data": data})
    return result["submitAgentExtraction"]


def report_scraped_item_error(
    item_id: int,
    message: str,
    *,
    is_fatal: bool = False,
) -> dict[str, Any]:
    """Report a processing error for a checked-out item."""
    query = """
    mutation ReportScrapedItemError($data: ScrapedItemErrorInput!) {
      reportScrapedItemError(data: $data)
    }
    """

    result = graphql_request(
        query,
        {
            "data": {
                "itemId": item_id,
                "message": message,
                "isFatal": is_fatal,
            },
        },
    )
    return {"ok": bool(result.get("reportScrapedItemError"))}
