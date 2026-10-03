"""Wap.Store product payload normalization."""

from __future__ import annotations

import json
import logging
from typing import NamedTuple

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


class _Page(NamedTuple):
    """The listing item every unit of one page shares."""

    page_id: str
    name: str
    url: str


class _Unit(NamedTuple):
    """What tells one buyable unit of a page apart from the others."""

    external_id: str
    options: list[VariantOption]
    selection: VariantSelection | None


class WapStoreNormalizer:
    """Normalize one Wap.Store listing item into the units it sells.

    Wap.Store describes buyable units with two attributes. ``simples`` lists
    the units inside one page, each with its own sku, price and stock -- the
    flavors of the 1 kg whey, the weights of Daily Whey. ``unico`` lists sibling
    pages, one product id per value, so it only says which value this page is.
    A page with ``simples`` yields one offer per value, keyed by the page id and
    the value id; a page without it is a single unit keyed by its own id.
    """

    provider = "wapstore"

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Normalize one Wap.Store unit, or skip unusable source data."""
        external_id = str(raw.get("id") or "")
        name_value = raw.get("nome") or raw.get("name")
        if not external_id or not name_value:
            logger.debug(
                "Skipping malformed Wap.Store item %s without id or name",
                external_id or "<missing>",
            )
            return None
        name = str(name_value)
        page_url = self._build_product_url(raw, base_url)
        if not is_http_url(page_url):
            logger.warning(
                "Skipping Wap.Store item without valid URL: %s",
                external_id,
            )
            return None

        page = _Page(page_id=external_id, name=name, url=page_url)
        page_options = self._page_options(raw, external_id)
        units = self._simples_values(raw)
        if units is None:
            offers = [
                self._offer(raw, page, _Unit(external_id, page_options, None)),
            ]
        else:
            attribute, values = units
            offers = [
                self._offer(
                    value,
                    page,
                    _Unit(
                        external_id=f"{external_id}-{value['idAtributoValor']}",
                        options=[
                            *page_options,
                            VariantOption(name=attribute, value=str(value["label"])),
                        ],
                        selection=VariantSelection(
                            kind="form_option",
                            parameters={attribute: str(value["label"])},
                        ),
                    ),
                )
                for value in values
            ]
        return ScrapedProductInput(
            store_slug=store_slug,
            provider=self.provider,
            provider_product_id=external_id,
            page_url=page_url,
            category=category,
            api_context=self._build_product_context(raw),
            offers=offers,
            coverage=[
                coverage("variants", complete=units is not None),
                coverage("sellers", complete=True),
                coverage("offers", complete=units is not None),
                coverage("payment_prices", complete=True),
            ],
        )

    def _offer(self, source: dict, page: _Page, unit: _Unit) -> ScrapedOfferInput:
        """Build one buyable unit from the item or one of its attribute values."""
        external_id = unit.external_id
        price = parse_positive_price(self._extract_raw_price(source))
        if price is None:
            # Kept: dropping the unit leaves its previous price standing.
            logger.warning("Wap.Store unit %s has no usable price", external_id)
        # Zero stock is a reading, not an absence: `or` would turn it into None.
        raw_stock = source.get("estoque")
        stock_quantity = parse_optional_int(
            raw_stock if raw_stock is not None else source.get("balance"),
        )
        sku = str(source.get("sku") or "").strip()
        return ScrapedOfferInput(
            external_id=external_id,
            offer_url=page.url,
            name=page.name,
            price=price,
            stock_quantity=stock_quantity if price is not None else 0,
            stock_status=self._resolve_stock_status(stock_quantity, price),
            ean=str(source.get("ean") or source.get("gtin") or ""),
            sku=sku,
            # The platform sells only the store's own stock.
            seller=SellerInput(is_channel_owner=True),
            prices=self._prices(source) if price is not None else [],
            variant_context=VariantContext(
                provider=self.provider,
                provider_product_id=page.page_id,
                provider_variant_id=sku or external_id,
                title=page.name,
                options=unit.options,
                selection=unit.selection,
            ),
        )

    @staticmethod
    def _simples_values(raw: dict) -> tuple[str, list[dict]] | None:
        """Return the in-page attribute and its buyable values, when published."""
        attributes = raw.get("atributos")
        simples = attributes.get("simples") if isinstance(attributes, dict) else None
        if not isinstance(simples, dict):
            return None
        values = [
            value
            for value in simples.get("valores") or []
            if isinstance(value, dict)
            and value.get("idAtributoValor") is not None
            and value.get("label")
        ]
        if not values or not simples.get("nome"):
            return None
        return str(simples["nome"]), values

    @staticmethod
    def _page_options(raw: dict, page_id: str) -> list[VariantOption]:
        """Return the ``unico`` value this page is, read from the sibling list."""
        attributes = raw.get("atributos")
        unico = attributes.get("unico") if isinstance(attributes, dict) else None
        if not isinstance(unico, dict) or not unico.get("nome"):
            return []
        for value in unico.get("valores") or []:
            product = value.get("produto") if isinstance(value, dict) else None
            if isinstance(product, dict) and str(product.get("id")) == page_id:
                label = str(value["label"])
                return [VariantOption(name=str(unico["nome"]), value=label)]
        return []

    def _build_product_url(self, item: dict, base_url: str) -> str:
        """Build the canonical product URL from a listing item."""
        link_slug = item.get("link") or item.get("slug") or item.get("url")
        if not link_slug:
            return ""
        value = str(link_slug)
        if value.startswith("http"):
            return value
        return f"{base_url}/{value.lstrip('/')}"

    @staticmethod
    def _prices(source: dict) -> list[PriceInput]:
        """Read ``por``, ``de``, the cash price and the installment plan.

        ``vista`` is the price paid at once; the store does not name the
        method, so its scope is ``cash`` and it already includes the published
        ``descontoVista``.
        """
        precos = source.get("precos")
        if not isinstance(precos, dict):
            price = parse_positive_price(source.get("price"))
            return (
                [PriceInput(role="payable", amount=price, source_field="price")]
                if price is not None
                else []
            )
        prices: list[PriceInput] = []
        if (por := parse_positive_price(precos.get("por"))) is not None:
            prices.append(
                PriceInput(role="payable", amount=por, source_field="precos.por"),
            )
        if (de := parse_positive_price(precos.get("de"))) is not None:
            prices.append(
                PriceInput(role="reference", amount=de, source_field="precos.de"),
            )
        if (vista := parse_positive_price(precos.get("vista"))) is not None:
            rate = parse_positive_price(precos.get("descontoVista"))
            prices.append(
                PriceInput(
                    role="payable",
                    amount=vista,
                    source_field="precos.vista",
                    payment_scope="cash",
                    payment_label_raw="vista",
                    composition="known" if rate is not None else "unknown",
                    included_adjustments=(
                        [{"kind": "payment_discount", "rate": str(rate)}]
                        if rate is not None
                        else []
                    ),
                ),
            )
        prices.extend(
            option
            for plan in precos.get("parcelamento") or []
            if isinstance(plan, dict) and (option := _installment(plan))
        )
        return prices

    def _extract_raw_price(self, item: dict) -> object:
        """Extract the price token used by the Wap.Store payload."""
        prices = item.get("precos")
        if isinstance(prices, dict):
            return prices.get("por") or prices.get("vista")
        return item.get("price")

    def _resolve_stock_status(
        self,
        stock_quantity: int | None,
        price: float | None,
    ) -> StockReading:
        """Treat absent/positive stock as available, but never a unit with no price."""
        if price is not None and (stock_quantity is None or stock_quantity > 0):
            return StockReading.AVAILABLE
        return StockReading.OUT_OF_STOCK

    def _build_product_context(self, item: dict) -> str:
        """Build the structured source context used by the current spider."""
        payload = {
            "platform": self.provider,
            "product": {
                "id": item.get("id"),
                "name": item.get("nome") or item.get("name"),
                "slug": item.get("slug"),
                "url": item.get("url") or item.get("link"),
                "sku": item.get("sku"),
                "ean": item.get("ean") or item.get("gtin"),
                "prices": item.get("precos") or {},
                "stock_raw": item.get("estoque") or item.get("balance"),
            },
        }
        return json.dumps(payload, ensure_ascii=False)


def _installment(plan: dict) -> PriceInput | None:
    """Read one row of ``precos.parcelamento``; the method is not named."""
    total = parse_positive_price(plan.get("valorTotal"))
    count = parse_optional_int(plan.get("parcelas"))
    if total is None or count is None or count < 1:
        return None
    rate = parse_positive_price(plan.get("taxa"))
    return PriceInput(
        role="payable",
        amount=total,
        source_field="precos.parcelamento",
        payment_label_raw="parcelamento",
        installment_count=count,
        installment_amount=parse_positive_price(plan.get("valorParcela")),
        interest="yes" if rate is not None else "no",
    )
