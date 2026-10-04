"""The whole migration path on legacy data: backfills, a new crawl, projections.

The legacy state is what production had before identities: offers keyed by
store and SKU, price history, one VTEX SKU whose default seller was a third
party, and catalog links.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Brand, Product, ProductStore, Store
from offers.models import Offer, OfferPriceObservation, PriceObservation, StockStatus
from pricing.models import OfferScenarioProjection
from pricing.projections import ProjectionService
from scrapers.crawler.pipelines import CatalogPipeline
from scrapers.models import ScrapedItem, ScrapedPage
from scrapers.stores.blackskull import BlackSkullSpider

STORE = "black_skull"


def _legacy_offer(sku: str, price: str) -> Offer:
    offer = Offer.objects.create(
        store_slug=STORE,
        external_id=sku,
        pid="p1",
        current_price=Decimal(price),
        current_stock_status=StockStatus.AVAILABLE,
        url=f"https://www.blackskullusa.com.br/whey/p?skuId={sku}",
    )
    page, _created = ScrapedPage.objects.get_or_create(
        url="https://www.blackskullusa.com.br/whey/p",
        defaults={
            "store_slug": STORE,
            "api_context": {
                "platform": "vtex_legacy",
                "items": [
                    {
                        "itemId": "10",
                        "sellers": [{"sellerId": "1", "sellerDefault": True}],
                    },
                    {
                        "itemId": "20",
                        "sellers": [{"sellerId": "acme", "sellerDefault": True}],
                    },
                ],
            },
        },
    )
    ScrapedItem.objects.create(
        offer=offer,
        source_page=page,
        variant_context={
            "provider": "vtex",
            "provider_product_id": "p1",
            "provider_variant_id": sku,
            "title": "Whey",
        },
    )
    old = timezone.now() - timedelta(days=40)
    PriceObservation.objects.create(offer=offer, price=Decimal(1), observed_at=old)
    PriceObservation.objects.create(offer=offer, price=Decimal(price))
    return offer


class MigrationPathTests(TestCase):
    """From legacy rows to a gated ranking, nothing is invented or lost."""

    def setUp(self) -> None:
        """Two legacy SKUs: 10 sold by the store, 20 by seller 'acme'."""
        Store.objects.create(
            name="Black Skull", display_name="Black Skull", scraper_slug=STORE
        )
        brand = Brand.objects.create(name="bs", display_name="Black Skull")
        self.own = _legacy_offer("10", "120.00")
        self.third = _legacy_offer("20", "250.00")
        for name, offer in (("Own", self.own), ("Third", self.third)):
            product = Product.objects.create(name=name, brand=brand, is_published=True)
            ProductStore.objects.create(product=product, offer=offer)

    def _run(self, command: str, *args: str) -> str:
        out = StringIO()
        call_command(command, *args, stdout=out)
        return out.getvalue()

    def _crawl(self) -> None:
        spider = BlackSkullSpider()
        raw = {
            "productId": "p1",
            "productName": "Whey",
            "linkText": "whey",
            "items": [
                {
                    "itemId": "20",
                    "sellers": [
                        {
                            "sellerId": "1",
                            "sellerName": "Black Skull",
                            "sellerDefault": True,
                            "commertialOffer": {"Price": 99.9, "AvailableQuantity": 5},
                        },
                    ],
                },
            ],
        }
        for product in spider.process_raw_product(raw, "whey"):
            CatalogPipeline().process_item(product, spider)

    def test_the_path(self) -> None:
        """Backfills, a crawl and projections, end to end."""
        self._run("backfill_commercial_identity", "--apply")
        self._run("backfill_legacy_price_observations", "--apply")
        self.own.refresh_from_db()
        self.third.refresh_from_db()

        # Identity: the store's SKU and the third party's SKU keep their sellers.
        assert self.own.seller_account.is_channel_owner
        assert self.third.seller_account.external_id == "acme"
        # History: the 40-day-old R$ 1 is stale, never a current price.
        stale = OfferPriceObservation.objects.get(offer=self.own, amount=Decimal(1))
        assert stale.confirmed_at <= timezone.now() - timedelta(days=39)

        # A crawl now names seller 1 under SKU 20: a separate offer.
        self._crawl()
        self.third.refresh_from_db()
        moved = Offer.objects.get(external_id="20@owner")
        assert self.third.current_price == Decimal("250.00")
        assert moved.current_price == Decimal("99.90")

        # Projections price each linked offer at what the crawl read.
        ProjectionService().refresh()
        projected = OfferScenarioProjection.objects.filter(
            policy__key="listed",
            alternative="best",
        ).select_related("offer")
        assert {row.offer for row in projected} == {self.own, self.third}
        assert all(row.amount == row.offer.current_price for row in projected)
