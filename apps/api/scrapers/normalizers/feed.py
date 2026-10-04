"""A structured feed: listings, variants, sellers and their prices, as data.

Any store or marketplace that publishes (or is granted) a structured feed is
onboarded by configuration: a feed URL and its market. The format names every
dimension the domain needs, so a marketplace's sellers, a payment price or a
reference price need no new code. One listing per entry::

    {"id": "MLB123", "url": "...", "title": "...", "catalog_product_id": "",
     "complete": true,
     "variants": [{"id": "v1", "options": [{"name": "Sabor", "value": "..."}],
                   "gtin": "", "selection": {"variation": "v1"},
                   "offers": [{"id": "o1",
                               "seller": {"id": "123", "name": "Loja",
                                          "channel_owner": false},
                               "featured": true, "stock": "available",
                               "quantity": 10,
                               "prices": [{"role": "payable", "amount": "99.90",
                                           "payment_scope": "unknown"}]}]}]}
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ..capabilities import AdapterCapabilities
from ..contracts import (
    CoverageInput,
    PriceInput,
    ScrapedOfferInput,
    ScrapedProductInput,
    SellerInput,
    StockReading,
    VariantContext,
    VariantOption,
    VariantSelection,
)
from .parsing import coverage, is_http_url, parse_optional_int, parse_positive_price

if TYPE_CHECKING:
    from decimal import Decimal

logger = logging.getLogger(__name__)

STOCK_READINGS = {
    "available": StockReading.AVAILABLE,
    "last_units": StockReading.LAST_UNITS,
    "out_of_stock": StockReading.OUT_OF_STOCK,
    "preorder": StockReading.PREORDER,
    "backorder": StockReading.BACKORDER,
}
PRICE_FIELDS = (
    "payment_scope",
    "payment_method",
    "payment_label_raw",
    "payment_provider_raw",
    "interest",
    "capture_stage",
    "evidence_level",
    "composition",
)


class FeedNormalizer:
    """Normalize one feed listing into one offer per variant and seller."""

    provider = "feed"
    capabilities = AdapterCapabilities(
        version="1",
        variants="complete",
        sellers="named",
        payment_prices="complete",
        cart_quote="none",
        destination_delivery="none",
        rewards="none",
        selectable_route="variant_and_seller",
    )

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize one listing, skipping malformed variants and offers."""
        _ = base_url
        listing_id = str(raw.get("id") or "")
        page_url = str(raw.get("url") or "")
        if not listing_id or not is_http_url(page_url):
            logger.debug("Skipping feed listing without id or URL")
            return None
        title = str(raw.get("title") or "")
        offers: list[ScrapedOfferInput] = []
        dropped = False
        for variant in raw.get("variants") or []:
            if not isinstance(variant, dict) or not variant.get("id"):
                dropped = True
                continue
            for offer in variant.get("offers") or []:
                built = self._offer(listing_id, title, page_url, variant, offer)
                if built is None:
                    dropped = True
                else:
                    offers.append(built)
        if not offers:
            return None
        complete = bool(raw.get("complete")) and not dropped
        return ScrapedProductInput(
            store_slug=store_slug,
            provider=self.provider,
            provider_product_id=listing_id,
            page_url=page_url,
            category=category,
            api_context=json.dumps(
                {"platform": self.provider, "product": raw},
                ensure_ascii=False,
            ),
            offers=offers,
            coverage=_coverage(complete=complete),
        )

    def _offer(
        self,
        listing_id: str,
        title: str,
        page_url: str,
        variant: dict,
        offer: object,
    ) -> ScrapedOfferInput | None:
        if not isinstance(offer, dict):
            return None
        seller = offer.get("seller") or {}
        if not isinstance(seller, dict):
            return None
        variant_id = str(variant["id"])
        seller_id = str(seller.get("id") or "")
        owner = bool(seller.get("channel_owner"))
        if not seller_id and not owner:
            # A price without a seller is the variant's, not an offer's: the
            # feed format requires an id or the owner flag for every offer.
            return None
        prices = [p for p in map(_price, offer.get("prices") or []) if p is not None]
        # The offer's own price is the one that states no payment condition;
        # a method's price is an observation beside it, not the offer price.
        unstated = [
            p.amount
            for p in prices
            if p.role == "payable"
            and p.payment_scope == "unknown"
            and p.installment_count is None
        ]
        price: Decimal | None = min(unstated) if unstated else None
        stock = STOCK_READINGS.get(str(offer.get("stock")), StockReading.UNKNOWN)
        selection = variant.get("selection") or {}
        return ScrapedOfferInput(
            external_id=f"{variant_id}@{'owner' if owner else seller_id}",
            offer_url=str(offer.get("url") or page_url),
            name=title,
            price=price,
            stock_status=stock if price is not None else StockReading.OUT_OF_STOCK,
            stock_quantity=parse_optional_int(offer.get("quantity")),
            sku=str(offer.get("id") or variant_id),
            ean=str(variant.get("gtin") or ""),
            seller=SellerInput(
                external_id=seller_id,
                name=str(seller.get("name") or ""),
                is_channel_owner=owner,
            ),
            featured=bool(offer.get("featured")),
            prices=prices,
            variant_context=VariantContext(
                provider=self.provider,
                provider_product_id=listing_id,
                provider_variant_id=variant_id,
                title=title,
                options=[
                    VariantOption(name=str(o["name"]), value=str(o["value"]))
                    for o in variant.get("options") or []
                    if isinstance(o, dict) and o.get("name") and o.get("value")
                ],
                selection=(
                    VariantSelection(kind="query_parameter", parameters=selection)
                    if isinstance(selection, dict) and selection
                    else None
                ),
            ),
        )


def _price(raw: object) -> PriceInput | None:
    """Read one feed price; an unknown key is ignored, a bad amount drops it."""
    if not isinstance(raw, dict) or raw.get("role") not in ("payable", "reference"):
        return None
    amount = parse_positive_price(raw.get("amount"))
    if amount is None:
        return None
    extra = {key: raw[key] for key in PRICE_FIELDS if raw.get(key)}
    return PriceInput(
        role=raw["role"],
        amount=amount,
        source_field=str(raw.get("source_field") or "feed.prices"),
        installment_count=parse_optional_int(raw.get("installment_count")),
        installment_amount=parse_positive_price(raw.get("installment_amount")),
        **extra,
    )


def _coverage(*, complete: bool) -> list[CoverageInput]:
    """Return the coverage a feed entry states for its variants and sellers."""
    return [
        coverage("variants", complete=complete),
        coverage("sellers", complete=complete),
        coverage("offers", complete=complete),
        coverage("payment_prices", complete=complete),
    ]
