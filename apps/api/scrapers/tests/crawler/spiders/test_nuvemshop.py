"""Nuvemshop pages are read for the units they sell, not just the first one."""

from __future__ import annotations

import json
from decimal import Decimal
from operator import attrgetter
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from scrapy import Request
from scrapy.http import TextResponse

from offers.models import StockStatus
from scrapers.contracts import ScrapedProductInput
from scrapers.stores.dux import DuxSpider

PAGE = "https://duxhumanhealth.com/produtos/whey-protein-concentrado-pote-900g/"

LISTING = {
    "@type": "Product",
    "name": "Whey Protein Concentrado - Pote 900g",
    "sku": "410713079",
    "gtin13": "7898604470045",
    "offers": {
        "@type": "Offer",
        "url": PAGE,
        "price": "368.90",
        "availability": "http://schema.org/InStock",
    },
}


def _variant(variant_id: int, sku: str, flavor: str, stock: int) -> dict:
    """Return one entry of LS.variants as Nuvemshop serves it."""
    return {
        "product_id": 355799609,
        "id": variant_id,
        "sku": sku,
        "option0": flavor,
        "option1": None,
        "option2": None,
        "price_number": 368.9,
        "stock": stock,
        "available": stock > 0,
        "is_visible": True,
    }


PRODUCT_HTML = f"""
<html><body>
<form id="product_form" class="js-product-form" method="post">
  <label class="form-label" for="variation_1">Sabores:</label>
  <select name="variation[0]"><option>Caramelo Salgado</option></select>
</form>
<script>
  LS.variants = {
    json.dumps(
        [
            _variant(1559663995, "410713079", "Caramelo Salgado", 309),
            _variant(1559814846, "410713044", "Neutro", 0),
        ]
    )
};
</script>
</body></html>
"""


def _response(url: str, body: str, status: int, meta: dict) -> TextResponse:
    """Return a response to a request carrying the given meta."""
    request = Request(url, meta=meta)
    return TextResponse(url, body=body.encode(), status=status, request=request)


class NuvemshopProductPageTests(SimpleTestCase):
    """A listing only names a page; the page lists every unit it sells."""

    def setUp(self) -> None:
        """Create a Dux spider with a stats collector to inspect."""
        self.spider = DuxSpider()
        self.spider.crawler = MagicMock()
        self.spider.crawler.stats.get_value = MagicMock(return_value=None)

    def _product_page(self, body: str, status: int = 200) -> list[object]:
        """Parse one product page answered for the whey listing entry."""
        response = _response(
            PAGE,
            body,
            status,
            {"category": "produtos", "listing": LISTING},
        )
        return list(attrgetter("_parse_product")(self.spider)(response))

    def test_the_listing_asks_for_each_product_page(self) -> None:
        """The listing card carries no variants, so the page must be read."""
        listing_html = (
            f'<script type="application/ld+json">{json.dumps(LISTING)}</script>'
        )
        response = _response(
            f"{PAGE}?page=1",
            listing_html,
            200,
            {"category": "produtos", "page": 1},
        )

        requests = [
            item
            for item in attrgetter("_parse_category")(self.spider)(response)
            if isinstance(item, Request)
        ]

        assert requests[0].url == PAGE
        assert requests[0].meta["listing"] == LISTING

    def test_every_flavor_on_the_page_is_its_own_offer(self) -> None:
        """Caramelo Salgado and Neutro are two things to buy."""
        (product,) = self._product_page(PRODUCT_HTML)

        assert isinstance(product, ScrapedProductInput)
        offers = {offer.external_id: offer for offer in product.offers}
        assert set(offers) == {"410713079", "410713044"}
        neutro = offers["410713044"]
        assert neutro.price == Decimal("368.90")
        assert neutro.stock_status == StockStatus.OUT_OF_STOCK
        assert [o.model_dump() for o in neutro.variant_context.options] == [
            {"name": "Sabores", "value": "Neutro"},
        ]
        assert product.is_complete("offers")

    def test_each_offer_links_to_its_flavor_selected(self) -> None:
        """Nuvemshop opens the page on the unit named by ?variant=."""
        (product,) = self._product_page(PRODUCT_HTML)
        neutro = next(o for o in product.offers if o.external_id == "410713044")

        assert neutro.offer_url == f"{PAGE}?variant=1559814846"
        assert neutro.variant_context.selection is not None
        assert neutro.variant_context.selection.parameters == {"variant": "1559814846"}

    def test_the_listing_barcode_stays_with_the_unit_it_describes(self) -> None:
        """The listing's GTIN is the first unit's, not every flavor's."""
        (product,) = self._product_page(PRODUCT_HTML)
        eans = {offer.external_id: offer.ean for offer in product.offers}

        assert eans == {"410713079": "7898604470045", "410713044": ""}

    def test_a_lost_product_page_keeps_the_listing_unit_and_is_recorded(
        self,
    ) -> None:
        """Losing the page must not freeze the price nor pass as a full read."""
        (product,) = self._product_page("", status=503)

        assert [offer.external_id for offer in product.offers] == ["410713079"]
        assert not product.is_complete("offers")
        assert self.spider.crawler.stats.inc_value.call_args_list
