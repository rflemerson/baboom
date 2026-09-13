"""Tests for scraper admin workflows."""

from __future__ import annotations

from decimal import Decimal
from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Brand, Product, ProductStore, Store
from offers.models import PriceObservation, StockStatus
from scrapers.tests import _scraped_item


class ScrapedItemAdminWorkflowTests(TestCase):
    """The human admin flow carries a captured offer into the catalog."""

    def test_create_product_prefills_and_links_existing_offer(self) -> None:
        """Creating a product reuses the offer, price, and store identity."""
        user = get_user_model().objects.create(
            username="catalog-admin",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        Brand.objects.create(name="growth", display_name="Growth")
        store = Store.objects.create(name="growth", display_name="Growth")
        item = _scraped_item(
            store_slug="growth",
            external_id="whey-450",
            name="Whey 450 g",
            price=Decimal("79.90"),
        )
        item.offer.url = "https://example.com/whey-450"
        item.offer.save(update_fields=["url"])
        PriceObservation.objects.create(
            offer=item.offer,
            price=Decimal("79.90"),
            stock_status=StockStatus.AVAILABLE,
        )

        action = self.client.post(
            reverse("admin:scrapers_scrapeditem_changelist"),
            {
                "action": "create_product_from_scraped_item",
                "_selected_action": [item.pk],
            },
        )
        assert action.status_code == HTTPStatus.FOUND
        add_url = action["Location"]
        assert f"source_offer={item.offer_id}" in add_url

        add_form = self.client.get(add_url)
        assert add_form.status_code == HTTPStatus.OK
        assert add_form.context["adminform"].form.initial["name"] == "Whey 450 g"
        listing = next(
            inline.formset
            for inline in add_form.context["inline_admin_formsets"]
            if inline.opts.model is ProductStore
        )
        assert listing.forms[0].initial["store"] == store.pk
        assert listing.forms[0].initial["price"] == Decimal("79.90")

        post_data = {
            "name": "Whey 450 g",
            "kind": Product.Kind.SIMPLE,
            "brand": Brand.objects.get(name="growth").pk,
            "net_mass": "450",
            "ean": "",
            "description": "",
            "packaging": Product.Packaging.CONTAINER,
            "category": "",
            "_save": "Save",
        }
        for inline in add_form.context["inline_admin_formsets"]:
            prefix = inline.formset.prefix
            post_data[f"{prefix}-TOTAL_FORMS"] = str(inline.formset.total_form_count())
            post_data[f"{prefix}-INITIAL_FORMS"] = "0"
            post_data[f"{prefix}-MIN_NUM_FORMS"] = "0"
            post_data[f"{prefix}-MAX_NUM_FORMS"] = "1000"
            if inline.opts.model is ProductStore:
                post_data.update(
                    {
                        f"{prefix}-0-store": str(store.pk),
                        f"{prefix}-0-external_id": item.offer.external_id,
                        f"{prefix}-0-product_link": item.offer.url,
                        f"{prefix}-0-price": "79.90",
                        f"{prefix}-0-stock_status": StockStatus.AVAILABLE,
                    },
                )

        saved = self.client.post(add_url, post_data)
        assert saved.status_code == HTTPStatus.FOUND
        product = Product.objects.get(name="Whey 450 g")
        assert ProductStore.objects.get(product=product).offer_id == item.offer_id
        assert PriceObservation.objects.filter(offer=item.offer).count() == 1
