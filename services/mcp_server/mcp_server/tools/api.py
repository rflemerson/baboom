import os
from typing import Any

import requests


class APIError(RuntimeError):
    pass


def _graphql_url() -> str:
    url = os.getenv("BACKEND_GRAPHQL_URL")
    if not url:
        raise APIError("BACKEND_GRAPHQL_URL não configurado.")
    return url


def _headers() -> dict[str, str]:
    api_key = os.getenv("BACKEND_API_KEY")
    if not api_key:
        raise APIError("BACKEND_API_KEY não configurado.")
    return {
        "Content-Type": "application/json",
        "X-API-KEY": api_key,
    }


def graphql_request(
    query: str, variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = requests.post(
        _graphql_url(),
        json={"query": query, "variables": variables or {}},
        headers=_headers(),
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, dict):
        raise APIError("Resposta GraphQL inválida.")
    if payload.get("errors"):
        raise APIError(str(payload["errors"]))
    if not isinstance(payload.get("data"), dict):
        raise APIError("Resposta GraphQL sem dados.")
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
    query = (
        "query($itemId: Int!) { reviewItem(itemId: $itemId) {"
        + ITEM_FIELDS
        + "} reviewExtraction(itemId: $itemId) { extractedProduct imageReport } }"
    )
    return graphql_request(query, {"itemId": item_id})


def review_action(action: str, item_id: int) -> dict:
    if action not in {"heartbeat", "release", "ignore"}:
        raise ValueError("Ação de revisão desconhecida.")
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
        id name brandId brandName categoryId categoryName ean netMass massUnit packaging isPublished
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
        raise ValueError("Referência de catálogo desconhecida.")
    field = fields[kind]
    query = (
        "query($search: String!, $limit: Int!) { "
        + field
        + "(search: $search, limit: $limit) { id name } }"
    )
    return graphql_request(query, {"search": search, "limit": limit})[field]


def approve_scraped_item(payload: dict) -> dict:
    query = """
    mutation($data: ScrapedItemApprovalInput!) {
      approveScrapedItem(data: $data) {
        product { id name brandId brandName categoryId categoryName ean netMass massUnit packaging isPublished }
        errors { field message }
      }
    }
    """
    result = graphql_request(query, {"data": payload})["approveScrapedItem"]
    if result.get("errors"):
        raise APIError(str(result["errors"]))
    if not result.get("product"):
        raise APIError("Aprovação não retornou produto.")
    return result["product"]


def submit_agent_extraction(data: dict[str, Any]) -> dict[str, Any]:
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
    item_id: int, message: str, is_fatal: bool = False
) -> dict[str, Any]:
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
