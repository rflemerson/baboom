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
    if payload.get("errors"):
        raise APIError(str(payload["errors"]))

    return payload["data"]


def checkout_scraped_item() -> dict[str, Any] | None:
    query = """
    mutation CheckoutScrapedItem {
      checkoutScrapedItem {
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
        sourcePageApiContext
        sourcePageHtmlStructuredData
      }
    }
    """

    data = graphql_request(query)
    return data.get("checkoutScrapedItem")


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
