"""Tests for scraper persistence services."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from offers.models import Offer, PriceObservation
from scrapers.contracts import (
    ScrapedItemIngestionInput,
    ScrapedOfferInput,
    ScrapedProductInput,
    VariantContext,
    VariantOption,
    VariantSelection,
)
from scrapers.models import ScrapedItem, ScrapedPage
from scrapers.services import ScraperService
from scrapers.tests import EXPECTED_PRICE_HISTORY_RECORDS_AFTER_UPDATE


class ScrapedItemIngestionInputTests(SimpleTestCase):
    """Unit tests for scraper ingestion DTO normalization."""

    def test_normalizes_invalid_ean_suffix_to_blank(self) -> None:
        """VTEX bundle labels with GTIN-looking prefixes should not hit the DB."""
        input_data = ScrapedItemIngestionInput(
            store_slug="black_skull",
            external_id="445",
            ean="7898708737105KIT",
        )

        assert input_data.ean == ""

    def test_normalizes_descriptive_ean_to_blank(self) -> None:
        """Descriptive bundle labels are not valid EAN/GTIN identifiers."""
        input_data = ScrapedItemIngestionInput(
            store_slug="max_titanium",
            external_id="333",
            ean="Whey Pro Morango +Horus Limao",
        )

        assert input_data.ean == ""

    def test_keeps_valid_gtin_14(self) -> None:
        """Valid GTIN values should still be persisted."""
        input_data = ScrapedItemIngestionInput(
            store_slug="black_skull",
            external_id="445",
            ean="7898708737105",
        )

        assert input_data.ean == "7898708737105"


class OfferObservationTests(TestCase):
    """Tests for recording offers and price observations from scraped data."""

    def _ingest(self, **overrides: object) -> ScrapedItemIngestionInput:
        """Build a scraped-item ingestion payload with sensible defaults."""
        defaults: dict[str, object] = {
            "store_slug": "test_store",
            "external_id": "TEST123",
            "name": "Test Whey 900g",
            "price": Decimal("199.90"),
            "stock_status": "A",
        }
        defaults.update(overrides)
        return ScrapedItemIngestionInput(**defaults)

    def test_save_product_records_offer_and_observation_without_link(self) -> None:
        """An offer and its first price are recorded even with no catalog link."""
        ScraperService.save_product(self._ingest())

        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert offer.current_price == Decimal("199.90")
        assert offer.name == "Test Whey 900g"
        assert offer.price_observations.count() == 1
        # The source item is created and bound to the offer.
        assert ScrapedItem.objects.filter(offer=offer).count() == 1

    def test_repeated_same_price_does_not_duplicate_observation(self) -> None:
        """Re-seeing the same price keeps a single observation."""
        ScraperService.save_product(self._ingest())
        ScraperService.save_product(self._ingest())

        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert offer.price_observations.count() == 1

    def test_repeated_same_price_updates_changed_api_context(self) -> None:
        """Catalog context should stay fresh even when price/stock are unchanged."""
        payload = self._ingest(page_url="https://example.com/test-product")
        ScraperService.save_product(payload, api_context={"version": 1})
        ScraperService.save_product(payload, api_context={"version": 2})

        page = ScrapedPage.objects.get(url="https://example.com/test-product")
        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert page.api_context == {"version": 2}
        assert offer.price_observations.count() == 1

    def test_price_change_appends_new_observation(self) -> None:
        """A changed price appends a second observation to the series."""
        ScraperService.save_product(self._ingest())
        ScraperService.save_product(self._ingest(price=Decimal("179.90")))

        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert (
            offer.price_observations.count()
            == EXPECTED_PRICE_HISTORY_RECORDS_AFTER_UPDATE
        )
        assert offer.current_price == Decimal("179.90")
        latest = PriceObservation.objects.filter(offer=offer).latest("observed_at")
        assert latest.price == Decimal("179.90")

    def test_missing_price_records_offer_without_observation(self) -> None:
        """An offer with no price is still tracked, but logs no observation."""
        ScraperService.save_product(self._ingest(price=None))

        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert offer.current_price is None
        assert offer.price_observations.count() == 0


class VariantIngestionTests(TestCase):
    """A page that sells several units yields several offers and one page."""

    URL = "https://example.com/products/whey"
    UNITS_ON_THE_PAGE = 2

    def _variant(
        self,
        external_id: str,
        price: str,
        title: str,
    ) -> ScrapedProductInput:
        return self._page((external_id, price, title))

    def _page(
        self,
        *units: tuple[str, str, str],
    ) -> ScrapedProductInput:
        """Build one page aggregate containing the supplied buyable units."""
        return ScrapedProductInput(
            store_slug="test_store",
            provider="shopify",
            provider_product_id="product-123",
            page_url=self.URL,
            api_context={"platform": "shopify", "product": {"id": "product-123"}},
            offers=[
                ScrapedOfferInput(
                    external_id=external_id,
                    offer_url=f"{self.URL}?variant={external_id}",
                    name=f"Whey - {title}",
                    price=Decimal(price),
                    variant_context=VariantContext(
                        provider="shopify",
                        provider_product_id="product-123",
                        provider_variant_id=external_id,
                        title=title,
                        options=[VariantOption(name="Peso", value=title)],
                        selection=VariantSelection(
                            kind="query_parameter",
                            parameters={"variant": external_id},
                        ),
                    ),
                )
                for external_id, price, title in units
            ],
        )

    def test_two_units_share_one_page_and_keep_their_own_offer(self) -> None:
        """The page is where they are sold; the offer is what is sold."""
        ScraperService.save_product_snapshot(
            self._page(
                ("111", "129.90", "1kg"),
                ("222", "229.90", "2kg"),
            ),
        )

        assert ScrapedPage.objects.count() == 1
        assert ScrapedItem.objects.count() == self.UNITS_ON_THE_PAGE
        offers = Offer.objects.order_by("external_id")
        assert [offer.external_id for offer in offers] == ["111", "222"]
        assert [offer.current_price for offer in offers] == [
            Decimal("129.90"),
            Decimal("229.90"),
        ]

    def test_each_offer_links_to_its_own_unit(self) -> None:
        """The stored link opens the unit that was priced, not the page."""
        ScraperService.save_product_snapshot(self._variant("111", "129.90", "1kg"))

        offer = Offer.objects.get(external_id="111")
        assert offer.url == f"{self.URL}?variant=111"
        assert ScrapedPage.objects.get().url == self.URL

    def test_the_context_says_which_unit_without_interpreting_it(self) -> None:
        """It records where to look, never what the label says.

        Reading mass or flavour off a variant title here would compete with
        the label, which is the only place either is actually stated.
        """
        ScraperService.save_product_snapshot(self._variant("111", "129.90", "1kg"))

        context = ScrapedItem.objects.get().variant_context
        assert context["provider_variant_id"] == "111"
        assert context["options"] == [{"name": "Peso", "value": "1kg"}]
        assert context["selection"]["parameters"]["variant"] == "111"
        assert "net_mass" not in context
        assert "flavor" not in context

    def test_snapshot_keeps_page_context_and_each_unit_context_separate(self) -> None:
        """The page owns API context while each item owns its variant context."""
        product = self._page(
            ("111", "129.90", "1kg"),
            ("222", "229.90", "2kg"),
        )
        ScraperService.save_product_snapshot(product)

        page = ScrapedPage.objects.get()
        assert page.api_context == {
            "platform": "shopify",
            "product": {"id": "product-123"},
        }
        items = ScrapedItem.objects.order_by("offer__external_id")
        assert [item.variant_context["provider_variant_id"] for item in items] == [
            "111",
            "222",
        ]

    def test_running_again_updates_rather_than_duplicates(self) -> None:
        """A second crawl of the same page must not double the catalog."""
        for _ in range(2):
            ScraperService.save_product_snapshot(
                self._page(
                    ("111", "129.90", "1kg"),
                    ("222", "229.90", "2kg"),
                ),
            )

        assert Offer.objects.count() == self.UNITS_ON_THE_PAGE
        assert ScrapedItem.objects.count() == self.UNITS_ON_THE_PAGE
        assert ScrapedPage.objects.count() == 1
