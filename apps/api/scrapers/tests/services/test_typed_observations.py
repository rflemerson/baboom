"""Ingestion keeps every price a source states, with what it means."""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from django.test import TestCase

from offers.models import (
    CollectionCoverage,
    FeaturedOfferObservation,
    Offer,
    OfferPriceObservation,
    PaymentScope,
)
from scrapers.crawler.pipelines import CatalogPipeline
from scrapers.stores.dux import DuxSpider
from scrapers.stores.growth import GrowthSpider
from scrapers.stores.max_titanium import MaxTitaniumSpider

if TYPE_CHECKING:
    from scrapers.contracts import ScrapedProductInput
    from scrapers.crawler.base import CatalogSpider

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "pricing"


def _payload(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))[
        "payload"
    ]


def _save(spider: CatalogSpider, products: list[ScrapedProductInput]) -> None:
    for product in products:
        CatalogPipeline().process_item(product, spider)


def _vtex_raw(sellers: list[dict]) -> dict:
    payload = _payload("max_titanium")
    return {
        "productId": payload["productId"],
        "productName": payload["productName"],
        "linkText": "whey",
        "items": [{"itemId": payload["itemId"], "sellers": sellers}],
    }


class VtexObservationTests(TestCase):
    """Max Titanium: the catalog's Pix price becomes its own observation."""

    def setUp(self) -> None:
        """Ingest the real Max Titanium excerpt once."""
        self.spider = MaxTitaniumSpider()
        self.sellers = _payload("max_titanium")["sellers"]
        _save(
            self.spider, self.spider.process_raw_product(_vtex_raw(self.sellers), "w")
        )
        self.offer = Offer.objects.get()

    def test_the_pix_total_is_a_payable_price_of_the_pix_method(self) -> None:
        """R$ 96.03 by Pix, beside the R$ 99.00 selling price."""
        pix = OfferPriceObservation.objects.get(
            offer=self.offer,
            payment_method__code="pix",
        )

        assert pix.amount == Decimal("96.03")
        assert pix.payment_scope == PaymentScope.METHOD
        assert pix.installment_count == 1
        assert pix.currency_id == "BRL"
        assert self.offer.current_price == Decimal("99.00")

    def test_the_list_price_is_a_reference_never_payable(self) -> None:
        """ListPrice is the "de" price."""
        reference = OfferPriceObservation.objects.get(
            offer=self.offer,
            source_field="commertialOffer.ListPrice",
        )

        assert reference.role == "reference"
        assert reference.amount == Decimal("126.2")

    def test_the_selling_price_states_no_payment(self) -> None:
        """Unknown payment is not "any"."""
        base = OfferPriceObservation.objects.get(
            offer=self.offer,
            source_field="commertialOffer.Price",
        )

        assert base.payment_scope == PaymentScope.UNKNOWN
        assert base.payment_method is None

    def test_a_repeated_read_appends_nothing(self) -> None:
        """Observations change only when a value changes."""
        before = OfferPriceObservation.objects.count()

        _save(
            self.spider, self.spider.process_raw_product(_vtex_raw(self.sellers), "w")
        )

        assert OfferPriceObservation.objects.count() == before

    def test_a_changed_pix_price_appends_one_observation(self) -> None:
        """Only the condition that moved gets a new row."""
        before = OfferPriceObservation.objects.count()
        sellers = copy.deepcopy(self.sellers)
        for entry in sellers[0]["commertialOffer"]["Installments"]:
            if entry["PaymentSystemName"] == "Pix":
                entry["Value"] = entry["TotalValuePlusInterestRate"] = 95.0
        spider = MaxTitaniumSpider()

        _save(spider, spider.process_raw_product(_vtex_raw(sellers), "w"))

        assert OfferPriceObservation.objects.count() == before + 1

    def test_an_unknown_payment_group_keeps_its_name_and_no_method(self) -> None:
        """A method the adapter does not know is never classified."""
        sellers = copy.deepcopy(self.sellers)
        sellers[0]["commertialOffer"]["Installments"] = [
            {
                "Value": 98,
                "InterestRate": 0,
                "TotalValuePlusInterestRate": 98,
                "NumberOfInstallments": 1,
                "PaymentSystemName": "Carteira X",
                "PaymentSystemGroupName": "newWalletPaymentGroup",
                "Name": "Carteira X à vista",
            },
        ]
        spider = MaxTitaniumSpider()
        _save(spider, spider.process_raw_product(_vtex_raw(sellers), "w"))

        wallet = OfferPriceObservation.objects.get(payment_provider_raw="Carteira X")
        assert wallet.payment_method is None
        assert wallet.payment_scope == PaymentScope.METHOD
        assert wallet.payment_label_raw == "Carteira X à vista"

    def _without_pix(self) -> list[dict]:
        sellers = copy.deepcopy(self.sellers)
        offer = sellers[0]["commertialOffer"]
        offer["Installments"] = [
            entry
            for entry in offer["Installments"]
            if entry["PaymentSystemName"] != "Pix"
        ]
        return sellers

    def test_a_complete_read_without_pix_withdraws_it(self) -> None:
        """Absence is evidence only in a complete read of payment prices."""
        spider = MaxTitaniumSpider()
        _save(spider, spider.process_raw_product(_vtex_raw(self._without_pix()), "w"))

        pix = OfferPriceObservation.objects.get(payment_method__code="pix")
        assert pix.withdrawn_at is not None

    def test_a_repeated_read_confirms_the_standing_value(self) -> None:
        """Nothing is appended; the row is confirmed later."""
        before = OfferPriceObservation.objects.get(
            source_field="commertialOffer.Price",
        ).confirmed_at

        spider = MaxTitaniumSpider()
        _save(spider, spider.process_raw_product(_vtex_raw(self.sellers), "w"))

        after = OfferPriceObservation.objects.get(source_field="commertialOffer.Price")
        assert after.confirmed_at > before
        assert after.withdrawn_at is None

    def test_the_page_records_its_coverage(self) -> None:
        """Variants, sellers and offers were all read."""
        statuses = dict(
            CollectionCoverage.objects.values_list("dimension", "status"),
        )

        assert statuses["sellers"] == "complete"
        assert statuses["offers"] == "complete"


class VtexSellerTests(TestCase):
    """Every seller of a SKU is its own offer; the default is only featured."""

    def _sellers(self, default: str) -> list[dict]:
        base = _payload("max_titanium")["sellers"][0]
        store = copy.deepcopy(base) | {"sellerDefault": default == "1"}
        other = copy.deepcopy(base) | {
            "sellerId": "acme",
            "sellerName": "Acme",
            "sellerDefault": default == "acme",
        }
        other["commertialOffer"]["Price"] = 89.9
        return [store, other]

    def test_two_sellers_are_two_offers_with_their_own_prices(self) -> None:
        """Neither price overwrites the other."""
        spider = MaxTitaniumSpider()
        _save(spider, spider.process_raw_product(_vtex_raw(self._sellers("1")), "w"))

        prices = dict(Offer.objects.values_list("external_id", "current_price"))
        item_id = _payload("max_titanium")["itemId"]
        assert prices == {
            item_id: Decimal("99.00"),
            f"{item_id}@acme": Decimal("89.90"),
        }

    def test_a_new_default_seller_is_a_new_featured_observation(self) -> None:
        """The buy box moved; both offers and their history remain."""
        spider = MaxTitaniumSpider()
        _save(spider, spider.process_raw_product(_vtex_raw(self._sellers("1")), "w"))
        spider = MaxTitaniumSpider()
        _save(spider, spider.process_raw_product(_vtex_raw(self._sellers("acme")), "w"))

        featured = list(
            FeaturedOfferObservation.objects.order_by("observed_at", "pk").values_list(
                "offer__external_id",
                flat=True,
            ),
        )
        item_id = _payload("max_titanium")["itemId"]
        assert featured == [item_id, f"{item_id}@acme"]
        assert Offer.objects.filter(delisted_at__isnull=True).count() == len(featured)


class WapStoreObservationTests(TestCase):
    """Growth: the cash price says it already includes its 10% discount."""

    def test_vista_is_a_cash_price_that_includes_its_discount(self) -> None:
        """Selecting it never applies the cash discount again."""
        payload = _payload("growth")
        raw = {
            "id": payload["id"],
            "nome": payload["nome"],
            "link": "whey",
            "atributos": {
                "simples": {
                    "nome": payload["atributos_simples_nome"],
                    "valores": payload["atributos_simples_valores_first4"],
                },
            },
        }
        spider = GrowthSpider()
        _save(spider, spider.process_raw_product(raw, "w"))

        offer = Offer.objects.get(external_id="185-1")
        cash = OfferPriceObservation.objects.get(
            offer=offer,
            source_field="precos.vista",
        )
        assert cash.amount == Decimal("199.9")
        assert cash.payment_scope == PaymentScope.CASH
        assert cash.composition == "known"
        assert cash.included_adjustments == [
            {"kind": "payment_discount", "rate": "10"},
        ]
        assert offer.current_price == Decimal("222.11")
        assert OfferPriceObservation.objects.filter(
            offer=offer,
            source_field="precos.parcelamento",
        ).count() == len(payload["precos"]["parcelamento"])


class NuvemshopObservationTests(TestCase):
    """DUX: the formatted payment price becomes an exact cash price."""

    def test_payment_discount_string_is_parsed_exactly(self) -> None:
        """R$310,56 is three hundred and ten reais and fifty-six cents."""
        spider = DuxSpider()
        product = spider.normalizer.normalize_page(
            {"url": "https://duxhumanhealth.com/produtos/whey/", "name": "Whey"},
            _payload("dux_nutrition")["variants_first2"],
            ["Sabor"],
            store_slug=spider.STORE_SLUG,
            category="whey",
        )
        assert product is not None
        _save(spider, [spider.with_market(product)])

        cash = OfferPriceObservation.objects.get(
            offer__external_id="410713023",
            source_field="price_with_payment_discount_short",
        )
        assert cash.amount == Decimal("310.56")
        assert cash.payment_scope == PaymentScope.CASH
