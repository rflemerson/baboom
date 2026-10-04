"""VTEX product payload normalization shared by Search and GraphQL spiders."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, NamedTuple

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
from .parsing import coverage, is_http_url, parse_optional_int, parse_positive_price

if TYPE_CHECKING:
    from decimal import Decimal

logger = logging.getLogger(__name__)

# VTEX numbers the store's own seller "1"; any other id is a marketplace seller.
VTEX_CHANNEL_OWNER_SELLER_ID = "1"

# VTEX payment groups mapped to payment method codes. A group not listed keeps
# its published name and no method: an unknown method is never Pix or "any".
PAYMENT_GROUP_METHODS = {
    "creditCardPaymentGroup": "credit_card",
    "debitCardPaymentGroup": "debit_card",
    "bankInvoicePaymentGroup": "boleto",
    "instantPaymentPaymentGroup": "pix",
    "giftCardPaymentGroup": "gift_card",
}


class _Unit(NamedTuple):
    """What every seller of one SKU shares."""

    product_id: str
    product_name: str
    page_url: str
    sku: dict


class VtexNormalizer:
    """Normalize one VTEX product into one offer per SKU and seller.

    Every seller a SKU lists is its own offer. The store's own seller ("1")
    keeps the SKU id as its external id, so offers captured before sellers were
    kept stay the same rows; another seller's offer is ``<sku>@<seller>``. The
    default seller is marked ``featured``: a selection, not an identity.
    """

    provider = "vtex"
    capabilities = AdapterCapabilities(
        version="2",
        variants="complete",
        sellers="named",
        payment_prices="complete",
        cart_quote="none",
        destination_delivery="none",
        rewards="none",
        selectable_route="variant",
    )

    def __init__(self, *, context_platform: str = "vtex_legacy") -> None:
        """Keep the source-context envelope used by the calling VTEX API."""
        self.context_platform = context_platform

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize one VTEX product, skipping unusable SKUs individually."""
        product_id = str(raw.get("productId") or "")
        link_text = raw.get("linkText")
        page_url = f"{base_url}/{link_text}/p" if link_text else ""
        if not product_id or not is_http_url(page_url):
            logger.debug(
                "Skipping malformed VTEX product %s without id or valid URL",
                product_id or "<missing>",
            )
            return None

        items = raw.get("items") or []
        if not isinstance(items, list):
            logger.debug("Skipping malformed VTEX product %s items", product_id)
            return None
        product_name = str(raw.get("productName") or "")
        offers: list[ScrapedOfferInput] = []
        complete_items = 0
        complete_sellers = True
        for sku in items:
            if not isinstance(sku, dict):
                logger.debug("Skipping malformed VTEX item for product %s", product_id)
                complete_sellers = False
                continue
            unit = _Unit(product_id, product_name, page_url, sku)
            sku_offers, all_sellers = self._normalize_sku(unit)
            if sku_offers:
                complete_items += 1
            complete_sellers = complete_sellers and all_sellers
            offers.extend(sku_offers)

        if not offers:
            return None

        variants_complete = complete_items == len(items)
        return ScrapedProductInput(
            store_slug=store_slug,
            provider=self.provider,
            provider_product_id=product_id,
            page_url=page_url,
            category=category,
            api_context=self._build_product_context(raw),
            offers=offers,
            coverage=[
                coverage("variants", complete=variants_complete),
                coverage("sellers", complete=complete_sellers),
                coverage("offers", complete=variants_complete and complete_sellers),
                coverage("payment_prices", complete=True),
            ],
        )

    def _normalize_sku(self, unit: _Unit) -> tuple[list[ScrapedOfferInput], bool]:
        """Return the offers of every seller of one SKU, and whether all parsed."""
        item_id = str(unit.sku.get("itemId") or "")
        sellers = unit.sku.get("sellers") or []
        if not item_id or not isinstance(sellers, list) or not sellers:
            logger.debug("Skipping VTEX item %s without id or seller", item_id)
            return [], False
        named = [seller for seller in sellers if isinstance(seller, dict)]
        anonymous = [seller for seller in named if not seller.get("sellerId")]
        if anonymous and len(named) > 1:
            # Two sellers, one without an id: the anonymous one cannot be told
            # apart from the next run's, so only identified sellers are kept.
            named = [seller for seller in named if seller.get("sellerId")]
        offers: list[ScrapedOfferInput] = []
        for seller in named:
            try:
                offer = self._seller_offer(unit, item_id, seller)
            except (
                AttributeError,
                KeyError,
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                logger.debug("Skipping malformed VTEX seller of %s: %s", item_id, exc)
                offer = None
            if offer is not None:
                offers.append(offer)
        return offers, len(offers) == len(sellers)

    def _seller_offer(
        self,
        unit: _Unit,
        item_id: str,
        seller: dict,
    ) -> ScrapedOfferInput | None:
        """Build one seller's offer of one SKU."""
        commercial = seller.get("commertialOffer") or {}
        if not isinstance(commercial, dict):
            logger.debug("Skipping malformed VTEX item %s commercial offer", item_id)
            return None
        price = parse_positive_price(commercial.get("Price"))
        if price is None:
            # An unavailable VTEX SKU commonly reports price zero. Dropping it
            # would leave the previous price standing as if still on sale.
            logger.warning("VTEX item %s has no usable price", item_id)
        stock_quantity = parse_optional_int(commercial.get("AvailableQuantity"))
        seller_input = self._seller_input(seller)
        external_id = (
            item_id
            if seller_input is None or seller_input.is_channel_owner
            else f"{item_id}@{seller_input.external_id}"
        )
        sku_name = str(unit.sku.get("nameComplete") or unit.sku.get("name") or "")
        return ScrapedOfferInput(
            external_id=external_id,
            offer_url=f"{unit.page_url}?skuId={item_id}",
            name=sku_name or unit.product_name,
            price=price,
            stock_quantity=stock_quantity if price is not None else 0,
            stock_status=_stock(price, stock_quantity, commercial.get("IsAvailable")),
            sku=item_id,
            ean=str(unit.sku.get("ean") or ""),
            seller=seller_input,
            featured=bool(seller.get("sellerDefault")),
            prices=self._prices(commercial, price),
            variant_context=VariantContext(
                provider=self.provider,
                provider_product_id=unit.product_id,
                provider_variant_id=item_id,
                title=str(unit.sku.get("name") or ""),
                options=self._sku_options(unit.sku),
                selection=VariantSelection(
                    kind="query_parameter",
                    parameters={"skuId": item_id},
                ),
            ),
        )

    @staticmethod
    def _prices(commercial: dict, price: Decimal | None) -> list[PriceInput]:
        """Read the selling price, the list price and every payment option."""
        if price is None:
            return []
        prices = [
            PriceInput(
                role="payable",
                amount=price,
                source_field="commertialOffer.Price",
            ),
        ]
        list_price = parse_positive_price(commercial.get("ListPrice"))
        if list_price is not None:
            prices.append(
                PriceInput(
                    role="reference",
                    amount=list_price,
                    source_field="commertialOffer.ListPrice",
                ),
            )
        prices.extend(
            option
            for entry in commercial.get("Installments") or []
            if isinstance(entry, dict) and (option := _installment(entry))
        )
        return prices

    @staticmethod
    def _seller_input(seller: dict) -> SellerInput | None:
        """Name the seller; VTEX seller "1" is the store that runs the channel.

        A seller entry without an id names nobody: the offer keeps no seller.
        """
        seller_id = str(seller.get("sellerId") or "")
        if not seller_id:
            return None
        return SellerInput(
            external_id=seller_id,
            name=str(seller.get("sellerName") or ""),
            is_channel_owner=seller_id == VTEX_CHANNEL_OWNER_SELLER_ID,
        )

    def _sku_options(self, sku: dict) -> list[VariantOption]:
        """Read VTEX variations in the order published by the SKU."""
        options: list[VariantOption] = []
        variations = sku.get("variations") or []
        if not isinstance(variations, list):
            return options
        for name in variations:
            values = sku.get(str(name)) or []
            if isinstance(values, list) and values:
                options.append(
                    VariantOption(name=str(name), value=str(values[0])),
                )
        return options

    def _build_product_context(self, item: dict) -> str:
        """Build the source context envelope for either VTEX API."""
        if self.context_platform == "vtex_graphql":
            product = {
                "productId": item.get("productId"),
                "productName": item.get("productName"),
                "brand": item.get("brand"),
                "linkText": item.get("linkText"),
                "clusterHighlights": item.get("clusterHighlights") or {},
            }
        else:
            product = {
                "productId": item.get("productId"),
                "productName": item.get("productName"),
                "brand": item.get("brand"),
                "linkText": item.get("linkText"),
                "categories": item.get("categories") or [],
                "categoryId": item.get("categoryId"),
            }
        payload = {
            "platform": self.context_platform,
            "product": product,
            "items": item.get("items") or [],
        }
        return json.dumps(payload, ensure_ascii=False)


def _stock(
    price: Decimal | None,
    quantity: int | None,
    is_available: object,
) -> StockReading:
    """Read stock from the quantity, or from ``IsAvailable`` when it is absent.

    No price is not for sale. Without a quantity, only an explicit
    ``IsAvailable`` says anything; with neither, stock is unknown.
    """
    if price is None:
        return StockReading.OUT_OF_STOCK
    if quantity is not None:
        return StockReading.AVAILABLE if quantity > 0 else StockReading.OUT_OF_STOCK
    if isinstance(is_available, bool):
        return StockReading.AVAILABLE if is_available else StockReading.OUT_OF_STOCK
    return StockReading.UNKNOWN


def _installment(entry: dict) -> PriceInput | None:
    """Read one payment option: a method, a count and the total it charges."""
    total = parse_positive_price(entry.get("TotalValuePlusInterestRate"))
    count = parse_optional_int(entry.get("NumberOfInstallments"))
    if total is None or count is None or count < 1:
        return None
    group = str(entry.get("PaymentSystemGroupName") or "")
    rate = parse_positive_price(entry.get("InterestRate"))
    return PriceInput(
        role="payable",
        amount=total,
        source_field="commertialOffer.Installments",
        payment_scope="method",
        payment_method=PAYMENT_GROUP_METHODS.get(group, ""),
        payment_label_raw=str(entry.get("Name") or group),
        payment_provider_raw=str(entry.get("PaymentSystemName") or ""),
        installment_count=count,
        installment_amount=parse_positive_price(entry.get("Value")),
        interest="yes" if rate is not None else "no",
    )
