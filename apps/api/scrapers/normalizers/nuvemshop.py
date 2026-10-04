"""Nuvemshop product normalization, from the product page or its listing."""

from __future__ import annotations

import json
import logging
from typing import Any, NamedTuple

from ..capabilities import AdapterCapabilities
from ..contracts import (
    PriceInput,
    ScrapedOfferInput,
    ScrapedProductInput,
    SellerInput,
    StockReading,
    VariantContext,
    VariantOption,
    VariantSelection,
)
from .parsing import (
    coverage,
    is_http_url,
    parse_optional_int,
    parse_positive_price,
)

logger = logging.getLogger(__name__)

IN_STOCK_MARKER = "instock"
OPTION_SLOTS = 3


class _Page(NamedTuple):
    """What every variant of one product page shares."""

    product_id: str
    url: str
    title: str
    option_names: list[str]
    listing_sku: str
    listing_ean: str


class NuvemshopNormalizer:
    """Normalize a Nuvemshop product into the units it sells.

    ``normalize_page`` reads the product page's ``LS.variants``: one unit per
    variant, keyed by its sku, reachable with ``?variant=<id>``. ``normalize``
    reads a listing's JSON-LD entry, which describes only the first unit, and
    serves when the page could not be read.
    """

    provider = "nuvemshop"
    capabilities = AdapterCapabilities(
        version="2",
        variants="complete",
        sellers="channel_owner_only",
        payment_prices="partial",
        cart_quote="none",
        destination_delivery="none",
        rewards="none",
        selectable_route="variant",
    )

    def page_url(self, listing: dict) -> str:
        """Return the product page a listing entry points to, without a query."""
        url = str(self._offer(listing).get("url") or listing.get("url") or "")
        page_url = url.split("?", maxsplit=1)[0]
        return page_url if is_http_url(page_url) else ""

    def normalize_page(
        self,
        listing: dict,
        variants: list[dict],
        option_names: list[str],
        *,
        store_slug: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize every visible variant of a product page."""
        page_url = self.page_url(listing)
        units = [variant for variant in variants if variant.get("is_visible", True)]
        if not page_url or not units:
            return None
        page = _Page(
            product_id=str(units[0].get("product_id") or listing.get("sku") or ""),
            url=page_url,
            title=str(listing.get("name") or ""),
            option_names=option_names,
            listing_sku=str(listing.get("sku") or ""),
            listing_ean=str(listing.get("gtin13") or ""),
        )
        offers = [
            offer
            for variant in units
            if (offer := self._variant_offer(variant, page)) is not None
        ]
        if not offers:
            return None
        return ScrapedProductInput(
            store_slug=store_slug,
            provider=self.provider,
            provider_product_id=page.product_id,
            page_url=page_url,
            category=category,
            api_context=json.dumps(
                {"platform": self.provider, "product": listing, "variants": units},
                ensure_ascii=False,
            ),
            offers=offers,
            coverage=[
                coverage("variants", complete=True),
                coverage("sellers", complete=True),
                coverage("offers", complete=True),
                coverage("payment_prices", complete=True),
            ],
        )

    def _variant_offer(self, variant: dict, page: _Page) -> ScrapedOfferInput | None:
        """Build the offer of one variant, or skip one without identity."""
        variant_id = str(variant.get("id") or "")
        sku = str(variant.get("sku") or "").strip()
        external_id = sku or variant_id
        if not variant_id or not external_id:
            return None
        price = parse_positive_price(variant.get("price_number"))
        if price is None:
            # Kept: dropping the unit leaves its previous price standing.
            logger.warning("Nuvemshop variant %s has no usable price", external_id)
        stock_quantity = parse_optional_int(variant.get("stock"))
        available = bool(variant.get("available")) and price is not None
        options = [
            VariantOption(name=name, value=str(value))
            for position, name in enumerate(page.option_names[:OPTION_SLOTS])
            if (value := variant.get(f"option{position}"))
        ]
        return ScrapedOfferInput(
            external_id=external_id,
            offer_url=f"{page.url}?variant={variant_id}",
            name=page.title,
            price=price,
            stock_quantity=stock_quantity if available else 0,
            stock_status=(
                StockReading.AVAILABLE if available else StockReading.OUT_OF_STOCK
            ),
            # The listing's barcode describes its own unit, not its siblings.
            ean=page.listing_ean if sku and sku == page.listing_sku else "",
            sku=sku,
            # The platform sells only the store's own stock.
            seller=SellerInput(is_channel_owner=True),
            prices=_variant_prices(variant) if price is not None else [],
            variant_context=VariantContext(
                provider=self.provider,
                provider_product_id=page.product_id,
                provider_variant_id=variant_id,
                title=page.title,
                options=options,
                selection=VariantSelection(
                    kind="query_parameter",
                    parameters={"variant": variant_id},
                ),
            ),
        )

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize one item and keep malformed source data out of the crawl."""
        identifier = str(raw.get("sku") or "") if isinstance(raw, dict) else "<missing>"
        try:
            return self._normalize(
                raw,
                store_slug=store_slug,
                base_url=base_url,
                category=category,
            )
        except (
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            # Warning, not error: the run must survive one malformed item.
            logger.warning("Skipping malformed Nuvemshop item %s: %s", identifier, exc)
            return None

    def _normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize the one unit represented by a JSON-LD product entry."""
        _ = base_url
        sku = str(raw.get("sku") or "")
        if not sku:
            logger.debug("Skipping malformed Nuvemshop item without SKU")
            return None

        offer = self._offer(raw)
        price = parse_positive_price(offer.get("price"))
        if price is None:
            # Kept: dropping the unit leaves its previous price standing.
            logger.warning("Nuvemshop item %s has no usable price", sku)

        offer_url = str(offer.get("url") or raw.get("url") or "")
        page_url = offer_url.split("?", maxsplit=1)[0]
        if not is_http_url(offer_url) or not is_http_url(page_url):
            logger.warning("Skipping Nuvemshop item without valid URL: %s", sku)
            return None

        title = str(raw.get("name") or "")
        availability = str(offer.get("availability") or "").lower()
        is_available = IN_STOCK_MARKER in availability
        stock_quantity = self._stock_quantity(offer) if is_available else 0
        context = VariantContext(
            provider=self.provider,
            provider_product_id=sku,
            provider_variant_id=sku,
            title=title,
            options=[],
            selection=None,
        )
        return ScrapedProductInput(
            store_slug=store_slug,
            provider=self.provider,
            provider_product_id=sku,
            page_url=page_url,
            category=category,
            api_context=json.dumps(
                {"platform": self.provider, "product": raw},
                ensure_ascii=False,
            ),
            offers=[
                ScrapedOfferInput(
                    external_id=sku,
                    offer_url=offer_url,
                    name=title,
                    price=price,
                    stock_quantity=stock_quantity if price is not None else 0,
                    stock_status=(
                        StockReading.AVAILABLE
                        if is_available and price is not None
                        else StockReading.OUT_OF_STOCK
                    ),
                    ean=str(raw.get("gtin13") or ""),
                    sku=sku,
                    variant_context=context,
                    seller=SellerInput(is_channel_owner=True),
                    prices=(
                        [
                            PriceInput(
                                role="payable",
                                amount=price,
                                source_field="offers.price",
                            ),
                        ]
                        if price is not None
                        else []
                    ),
                ),
            ],
        )

    def _offer(self, item: dict[str, Any]) -> dict[str, Any]:
        """Return the first JSON-LD offer object."""
        offers = item.get("offers")
        if isinstance(offers, list):
            offers = next((offer for offer in offers if isinstance(offer, dict)), None)
        return offers if isinstance(offers, dict) else {}

    def _stock_quantity(self, offer: dict[str, Any]) -> int | None:
        """Read the advertised inventory level, when present."""
        level = offer.get("inventoryLevel")
        value = level.get("value") if isinstance(level, dict) else None
        if value is None:
            return None
        try:
            return int(float(value))
        except TypeError, ValueError:
            return None


def _variant_prices(variant: dict) -> list[PriceInput]:
    """Read a variant's price, reference, payment price and installments.

    ``price_with_payment_discount_short`` is a formatted price paid at once
    with the store's payment discount; the field does not name the method.
    """
    prices: list[PriceInput] = []
    if (price := parse_positive_price(variant.get("price_number"))) is not None:
        prices.append(
            PriceInput(role="payable", amount=price, source_field="price_number"),
        )
    reference = parse_positive_price(variant.get("compare_at_price_number"))
    if reference is not None:
        prices.append(
            PriceInput(
                role="reference",
                amount=reference,
                source_field="compare_at_price_number",
            ),
        )
    discounted = parse_positive_price(variant.get("price_with_payment_discount_short"))
    if discounted is not None:
        prices.append(
            PriceInput(
                role="payable",
                amount=discounted,
                source_field="price_with_payment_discount_short",
                payment_scope="cash",
                payment_label_raw="payment discount",
                composition="partial",
                included_adjustments=[{"kind": "payment_discount"}],
            ),
        )
    prices.extend(_installments(variant.get("installments_data")))
    return prices


def _installments(raw: object) -> list[PriceInput]:
    """Read ``installments_data``: per gateway, per count, the total charged."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, dict):
        return []
    options: list[PriceInput] = []
    for gateway, plans in raw.items():
        if not isinstance(plans, dict):
            continue
        for count, plan in plans.items():
            if not isinstance(plan, dict) or not str(count).isdigit():
                continue
            total = parse_positive_price(plan.get("total_value"))
            if total is None:
                continue
            options.append(
                PriceInput(
                    role="payable",
                    amount=total,
                    source_field="installments_data",
                    payment_provider_raw=str(gateway),
                    payment_label_raw=str(gateway),
                    installment_count=int(count),
                    installment_amount=parse_positive_price(
                        plan.get("installment_value"),
                    ),
                    interest="no" if plan.get("without_interests") else "yes",
                ),
            )
    return options
