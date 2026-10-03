"""The price audit fixtures, read back through the normalizers that ingest them.

Each fixture is an excerpt, not a normalizer input. These tests rebuild the
smallest input each normalizer accepts from the excerpt, so the audit's claim
about which source field becomes ``current_price`` stays executable.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.test import SimpleTestCase

from scrapers.normalizers.nuvemshop import NuvemshopNormalizer
from scrapers.normalizers.shopify import ShopifyNormalizer
from scrapers.normalizers.vtex import VtexNormalizer
from scrapers.normalizers.wapstore import WapStoreNormalizer

if TYPE_CHECKING:
    from scrapers.contracts import ScrapedProductInput

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pricing"
STORES = (
    "black_skull",
    "max_titanium",
    "probiotica",
    "growth",
    "dux_nutrition",
    "dark_lab",
    "integral_medica",
    "soldiers_nutrition",
)
EVIDENCE_LEVELS = {"advertised", "terms", "theme_setting", "collection_name"}


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _price(product: ScrapedProductInput | None) -> Decimal | None:
    assert product is not None
    return product.offers[0].price


class FixtureMetadataTests(SimpleTestCase):
    """Every fixture says what it is, where it came from and when."""

    def test_store_fixtures_declare_an_excerpt_of_a_real_source(self) -> None:
        """An excerpt is evidence, never mistaken for a normalizer input."""
        for name in STORES:
            with self.subTest(name):
                fixture = _load(name)
                artifact = fixture["artifact"]
                assert artifact["kind"] == "source_excerpt"
                assert artifact["origin"] == "real"
                assert artifact["normalizer_input"] is False
                assert artifact["limits"]
                assert fixture["source_url"].startswith("https://")
                assert datetime.fromisoformat(fixture["fetched_at"]).tzinfo

    def test_raw_text_matches_are_marked_unclassified(self) -> None:
        """A page match on "pix" is mostly tracking pixels, not a price."""
        for name in ("dark_lab", "integral_medica", "soldiers_nutrition"):
            with self.subTest(name):
                assert _load(name)["raw_text_matches"]["classified"] is False

    def test_selected_evidence_names_its_level_and_scope(self) -> None:
        """Each excerpt says what it proves and what it covers."""
        benefits = _load("benefits")
        assert benefits["artifact"] == {"kind": "selected_evidence", "origin": "real"}
        for benefit in benefits["benefits"]:
            with self.subTest(benefit["source_url"]):
                assert benefit["evidence_level"] in EVIDENCE_LEVELS
                assert benefit["applies_to"]
                assert benefit["excerpts"]


class VtexFixtureTests(SimpleTestCase):
    """VTEX: the default seller's ``Price`` becomes the offer price."""

    def _normalize(self, name: str) -> ScrapedProductInput | None:
        payload = _load(name)["payload"]
        raw = {
            "productId": payload["productId"],
            "productName": payload["productName"],
            "linkText": "fixture",
            "items": [{"itemId": payload["itemId"], "sellers": payload["sellers"]}],
        }
        return VtexNormalizer().normalize(
            raw,
            store_slug=name,
            base_url="https://example.com",
            category="whey",
        )

    def test_offer_price_is_the_default_sellers_price(self) -> None:
        """Not ``ListPrice``, and not a payment-method total."""
        expected = {
            "black_skull": Decimal("99.9"),
            "max_titanium": Decimal(99),
            "probiotica": Decimal("252.49"),
        }
        for name, price in expected.items():
            with self.subTest(name):
                assert _price(self._normalize(name)) == price

    def test_max_titanium_publishes_a_lower_pix_total_the_offer_drops(self) -> None:
        """The catalog already prices Pix per method; the contract has no slot."""
        offer = _load("max_titanium")["payload"]["sellers"][0]["commertialOffer"]
        pix = [
            entry
            for entry in offer["Installments"]
            if entry["PaymentSystemName"] == "Pix"
        ]
        assert [Decimal(str(entry["Value"])) for entry in pix] == [Decimal("96.03")]
        assert _price(self._normalize("max_titanium")) == Decimal(99)


class ShopifyFixtureTests(SimpleTestCase):
    """Shopify: ``variant.price`` in cents; no payment price in the API."""

    def test_offer_price_is_the_variant_price_in_cents(self) -> None:
        """The theme's Pix discount never reaches the offer."""
        expected = {
            "dark_lab": Decimal("149.89"),
            "integral_medica": Decimal(227),
            "soldiers_nutrition": Decimal("145.9"),
        }
        normalizer = ShopifyNormalizer(price_int_is_cents=True)
        for name, price in expected.items():
            with self.subTest(name):
                payload = _load(name)["payload"]
                raw = {
                    "id": payload["product_id"],
                    "handle": "fixture",
                    "title": payload["title"],
                    "variants": [payload["variant"]],
                }
                product = normalizer.normalize(
                    raw,
                    store_slug=name,
                    base_url="https://example.com",
                    category="whey",
                )
                assert _price(product) == price


class WapStoreFixtureTests(SimpleTestCase):
    """Growth: ``precos.por`` wins over the cash price ``precos.vista``."""

    def test_offer_price_is_por_not_the_cash_price(self) -> None:
        """R$ 222.11 is stored; the 10% cash price R$ 199.90 is not."""
        payload = _load("growth")["payload"]
        raw = {
            "id": payload["id"],
            "nome": payload["nome"],
            "link": "fixture",
            "atributos": {
                "simples": {
                    "nome": payload["atributos_simples_nome"],
                    "valores": payload["atributos_simples_valores_first4"],
                },
            },
        }
        product = WapStoreNormalizer().normalize(
            raw,
            store_slug="growth",
            base_url="https://example.com",
            category="whey",
        )
        assert product is not None
        cash = Decimal(
            str(payload["atributos_simples_valores_first4"][0]["precos"]["vista"])
        )
        assert product.offers[0].price == Decimal("222.11")
        assert cash == Decimal("199.9")


class NuvemshopFixtureTests(SimpleTestCase):
    """DUX: ``price_number`` per variant, each variant its own price."""

    def test_each_variant_keeps_its_own_price(self) -> None:
        """The 5% payment price is a string the offer does not carry."""
        variants = _load("dux_nutrition")["payload"]["variants_first2"]
        product = NuvemshopNormalizer().normalize_page(
            {"url": "https://example.com/produtos/fixture/", "name": "Whey"},
            variants,
            ["Sabor"],
            store_slug="dux_nutrition",
            category="whey",
        )
        assert product is not None
        assert [offer.price for offer in product.offers] == [
            Decimal("326.9"),
            Decimal("368.9"),
        ]
        assert variants[0]["price_with_payment_discount_short"] == "R$310,56"
