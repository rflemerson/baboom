"""Tests for scraper admin workflows."""

from __future__ import annotations

from decimal import Decimal
from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Brand,
    Product,
    ProductStore,
    Store,
)
from offers.models import PriceObservation, StockStatus
from scrapers.tests.helpers import _scraped_item


class ScrapedItemAdminWorkflowTests(TestCase):
    """The human admin flow carries a captured offer into the catalog."""

    def setUp(self) -> None:
        """Log in a curator and capture a Growth offer with its price."""
        user = get_user_model().objects.create(
            username="catalog-admin",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        self.store = Store.objects.create(
            name="Growth",
            display_name="Growth",
            scraper_slug="growth",
        )
        self.item = _scraped_item(
            store_slug="growth",
            external_id="whey-450",
            name="Whey 450 g",
            price=Decimal("79.90"),
        )
        self.item.offer.url = "https://example.com/whey-450"
        self.item.offer.save(update_fields=["url"])
        PriceObservation.objects.create(
            offer=self.item.offer,
            price=Decimal("79.90"),
            stock_status=StockStatus.AVAILABLE,
        )

    def _act(self) -> str:
        """Run the link action on the item and return where it redirects."""
        response = self.client.post(
            reverse("admin:scrapers_scrapeditem_changelist"),
            {"action": "link_scraped_item_offer", "_selected_action": [self.item.pk]},
        )
        assert response.status_code == HTTPStatus.FOUND
        return response["Location"]

    def test_the_link_form_opens_with_the_offer_chosen(self) -> None:
        """The curator starts from the offer and only picks the catalog row."""
        add_url = self._act()

        assert f"offer={self.item.offer_id}" in add_url
        form = self.client.get(add_url).context["adminform"].form
        assert str(form.initial["offer"]) == str(self.item.offer_id)

    def test_linking_reuses_the_offer_its_price_and_its_store(self) -> None:
        """Saving the form links the captured offer without recording a price."""
        product = Product.objects.create(
            name="Whey 450 g",
            brand=Brand.objects.create(name="growth", display_name="Growth"),
            net_mass=Decimal(450),
        )

        response = self.client.post(
            self._act(),
            {
                "product": product.pk,
                "offer": self.item.offer_id,
                "affiliate_link": "",
                "_save": "Save",
            },
        )

        assert response.status_code == HTTPStatus.FOUND, response.context
        link = ProductStore.objects.get(product=product)
        assert link.offer_id == self.item.offer_id
        assert link.store == self.store
        assert self.item.offer.price_observations.count() == 1

    def test_an_already_linked_offer_opens_its_link(self) -> None:
        """A second click lands on the existing link instead of a duplicate."""
        product = Product.objects.create(
            name="Kit",
            brand=Brand.objects.create(name="growth", display_name="Growth"),
            kind=Product.Kind.COMBO,
        )
        link = ProductStore.objects.create(product=product, offer=self.item.offer)

        assert self._act().endswith(
            reverse("admin:core_productstore_change", args=[link.pk]),
        )
