"""Human-readable formatting helpers for review items."""

from typing import Any


def format_item_summary(item: dict[str, Any]) -> str:
    """Return a compact text summary of a scraped item."""
    structured_data = "yes" if item.get("sourcePageStructuredData") else "no"
    return "\n".join(
        [
            f"Item: {item.get('id')}",
            f"Status: {item.get('status')}",
            f"Store: {item.get('storeName') or item.get('storeSlug')}",
            f"External ID: {item.get('externalId')}",
            f"Name: {item.get('name')}",
            f"Price: {item.get('price')}",
            f"Stock: {item.get('stockStatus')}",
            f"Product link: {item.get('productLink')}",
            f"Source page: {item.get('sourcePageUrl')}",
            f"Source page ID: {item.get('sourcePageId')}",
            f"Has API context: {'yes' if item.get('sourcePageContext') else 'no'}",
            f"Has structured data: {structured_data}",
        ],
    )
