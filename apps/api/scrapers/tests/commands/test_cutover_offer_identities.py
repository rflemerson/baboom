"""Tests for scraper persistence services."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Brand, Product, ProductStore, Store
from offers.models import Offer, PriceObservation
from scrapers.models import ScrapedItem, ScrapedPage
from scrapers.tests.helpers import _raised


class OfferIdentityCutoverTests(TestCase):
    """Legacy identity transition is inspectable and never automatic."""

    def _legacy_offer(self, variants: list[dict[str, object]]) -> Offer:
        offer = Offer.objects.create(
            store_slug="test_store",
            external_id="product-123",
            pid="product-123",
            sku="SKU-111",
            current_price=Decimal("129.90"),
        )
        page = ScrapedPage.objects.create(
            store_slug="test_store",
            url="https://example.com/products/whey",
            api_context={
                "platform": "shopify",
                "product": {"id": "product-123"},
                "variants": variants,
            },
        )
        ScrapedItem.objects.create(offer=offer, source_page=page)
        PriceObservation.objects.create(offer=offer, price=Decimal("129.90"))
        return offer

    def _curated_link(self, offer: Offer) -> ProductStore:
        """Attach a catalog link to the old identity for cutover coverage."""
        brand = Brand.objects.create(name="test", display_name="Test")
        product = Product.objects.create(name="Whey", brand=brand)
        store = Store.objects.create(name="test_store", display_name="Test Store")
        return ProductStore.objects.create(product=product, store=store, offer=offer)

    def test_a_platform_that_keeps_its_identity_is_left_alone(self) -> None:
        """WapStore and Nuvemshop key a unit by the same id the legacy rows use.

        Nothing moves for them, so they must not be reported as ambiguous: that
        reading would archive rows that are already correct.
        """
        offer = Offer.objects.create(
            store_slug="growth",
            external_id="4518",
            pid="4518",
            sku="",
            current_price=Decimal("99.90"),
        )
        page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://example.com/produto/whey",
            api_context={"platform": "uappi_wapstore", "product": {"id": "4518"}},
        )
        ScrapedItem.objects.create(offer=offer, source_page=page)

        output = StringIO()
        call_command("cutover_offer_identities", stdout=output)

        report = output.getvalue()
        assert "growth/4518" not in report
        assert "0 legacy offers" in report

    def test_cutover_preview_does_not_write(self) -> None:
        """Operators can inspect the mapping before changing any row."""
        offer = self._legacy_offer([{"id": "variant-111", "sku": "SKU-111"}])
        output = StringIO()

        call_command("cutover_offer_identities", stdout=output)

        offer.refresh_from_db()
        assert offer.external_id == "product-123"
        assert "variant-111" in output.getvalue()

    def test_safe_cutover_separates_legacy_history_from_new_unit(self) -> None:
        """The curated link moves, while historical observations stay old."""
        offer = self._legacy_offer([{"id": "variant-111", "sku": "SKU-111"}])
        old_pk = offer.pk
        link = self._curated_link(offer)

        call_command("cutover_offer_identities", apply=True, stdout=StringIO())

        offer.refresh_from_db()
        assert offer.pk == old_pk
        link.refresh_from_db()
        assert link.offer_id != old_pk
        assert offer.external_id == "product-123"
        assert offer.current_price is None
        assert offer.delisted_at is not None
        assert offer.price_observations.count() == 1
        replacement = Offer.objects.get(pk=link.offer_id)
        assert replacement.external_id == "variant-111"
        assert replacement.current_price is None
        assert replacement.price_observations.count() == 0

    def test_ambiguous_cutover_requires_explicit_archival(self) -> None:
        """A many-unit page cannot invent which unit the old row represented."""
        offer = self._legacy_offer(
            [{"id": "variant-111", "sku": "OTHER"}, {"id": "variant-222"}],
        )
        link = self._curated_link(offer)

        _raised(
            lambda: call_command(
                "cutover_offer_identities", apply=True, stdout=StringIO()
            ),
            CommandError,
        )
        offer.refresh_from_db()
        assert offer.delisted_at is None

        call_command(
            "cutover_offer_identities",
            apply=True,
            archive_ambiguous=True,
            stdout=StringIO(),
        )
        offer.refresh_from_db()
        assert offer.delisted_at is not None
        assert offer.current_price is None
        link.refresh_from_db()
        assert link.offer_id is None

    def test_existing_variant_identity_receives_curated_link(self) -> None:
        """A variant already crawled keeps its own PK; the old row is archived."""
        old = self._legacy_offer([{"id": "variant-111", "sku": "SKU-111"}])
        link = self._curated_link(old)
        current = Offer.objects.create(
            store_slug="test_store",
            external_id="variant-111",
            pid="product-123",
            current_price=Decimal("99.90"),
        )

        call_command("cutover_offer_identities", apply=True, stdout=StringIO())

        link.refresh_from_db()
        old.refresh_from_db()
        current.refresh_from_db()
        assert link.offer_id == current.pk
        assert old.delisted_at is not None
        assert old.current_price is None
        assert current.current_price == Decimal("99.90")
