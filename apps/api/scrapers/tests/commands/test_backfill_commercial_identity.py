"""Offers captured before identities existed get them, without guessed sellers."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from commerce.models import SellerAccount
from core.models import Store
from offers.models import Offer
from scrapers.models import ScrapedItem, ScrapedPage


def _captured(store_slug: str, external_id: str, context: dict) -> Offer:
    offer = Offer.objects.create(
        store_slug=store_slug,
        external_id=external_id,
        pid="p1",
        current_price=Decimal("99.90"),
        options=[{"name": "Sabor", "value": "Baunilha"}],
    )
    page, _created = ScrapedPage.objects.get_or_create(
        url=f"https://example.com/{store_slug}/p1",
        defaults={"store_slug": store_slug, "api_context": context},
    )
    ScrapedItem.objects.create(
        offer=offer,
        source_page=page,
        variant_context={
            "provider": context["platform"],
            "provider_product_id": "p1",
            "provider_variant_id": external_id,
            "title": "Whey",
        },
    )
    return offer


def _vtex_context(seller_id: str | None) -> dict:
    sellers = [{"sellerId": seller_id, "sellerDefault": True}] if seller_id else []
    return {
        "platform": "vtex_legacy",
        "items": [{"itemId": "i1", "sellers": sellers}],
    }


class BackfillCommercialIdentityTests(TestCase):
    """Preview first; sellers only where the captured source names them."""

    def _run(self, *args: str) -> str:
        out = StringIO()
        call_command("backfill_commercial_identity", *args, stdout=out)
        return out.getvalue()

    def test_preview_writes_nothing(self) -> None:
        """Without --apply the report is all that happens."""
        offer = _captured("dark_lab", "50", {"platform": "shopify"})

        output = self._run()

        offer.refresh_from_db()
        assert "Would bind 1 offers" in output
        assert offer.listing_variant_id is None
        assert not SellerAccount.objects.exists()

    def test_apply_binds_a_shopify_offer_to_the_store(self) -> None:
        """Shopify sells only the store's stock."""
        offer = _captured("dark_lab", "50", {"platform": "shopify"})
        store = Store.objects.create(
            name="Dark Lab",
            display_name="Dark Lab",
            scraper_slug="dark_lab",
        )

        self._run("--apply")

        offer.refresh_from_db()
        store.refresh_from_db()
        assert offer.seller_account.is_channel_owner
        assert offer.listing_variant.options == [
            {"name": "Sabor", "value": "Baunilha"},
        ]
        assert store.seller_account == offer.seller_account
        assert ScrapedPage.objects.get().listing == offer.listing_variant.listing

    def test_vtex_seller_one_is_the_store(self) -> None:
        """The stored context names seller 1, the channel owner."""
        offer = _captured("black_skull", "i1", _vtex_context("1"))

        self._run("--apply")

        offer.refresh_from_db()
        assert offer.seller_account.is_channel_owner

    def test_vtex_without_a_named_seller_is_left_for_review(self) -> None:
        """No seller in the context: none is assumed."""
        offer = _captured("black_skull", "i1", _vtex_context(None))

        output = self._run("--apply")

        offer.refresh_from_db()
        assert offer.seller_account is None
        assert offer.listing_variant is not None
        assert "Without a seller, for review: 1" in output

    def test_an_offer_of_an_undeclared_store_is_reported(self) -> None:
        """No spider declares the market: nothing is invented."""
        _captured("unknown_store", "x", {"platform": "shopify"})

        output = self._run("--apply")

        assert "no spider declares its market" in output
