from typing import Any


def format_item_summary(item: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Item: {item.get('id')}",
            f"Status: {item.get('status')}",
            f"Loja: {item.get('storeName') or item.get('storeSlug')}",
            f"External ID: {item.get('externalId')}",
            f"Nome: {item.get('name')}",
            f"Preço: {item.get('price')}",
            f"Estoque: {item.get('stockStatus')}",
            f"Link produto: {item.get('productLink')}",
            f"Página fonte: {item.get('sourcePageUrl')}",
            f"Source page ID: {item.get('sourcePageId')}",
            f"Tem API context: {'sim' if item.get('sourcePageApiContext') else 'não'}",
            f"Tem structured data: {'sim' if item.get('sourcePageHtmlStructuredData') else 'não'}",
        ],
    )
