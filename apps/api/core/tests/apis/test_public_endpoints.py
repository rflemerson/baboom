"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

import json
from decimal import Decimal
from http import HTTPStatus

from django.test import TestCase, override_settings

from core.models import Brand, NutritionFacts, Product, ProductNutrition, Store
from core.tests.helpers import _link_offer


class PublicEndpointSecurityTests(TestCase):
    """Tests for public endpoint access rules."""

    def test_public_catalog_rest_query_without_api_key(self) -> None:
        """Public REST catalog requests should be allowed without API key."""
        response = self.client.get("/api/catalog/products/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert "public" in response["Cache-Control"]
        assert "s-maxage=21600" in response["Cache-Control"]
        assert payload["pageInfo"]["totalCount"] == 0

    def test_healthz_without_api_key(self) -> None:
        """Healthchecks should not depend on GraphQL authentication."""
        response = self.client.get("/healthz/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert payload == {"status": "ok"}

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz/$"])
    def test_healthz_skips_production_ssl_redirect(self) -> None:
        """Container healthchecks should receive a direct 200 in production."""
        response = self.client.get("/healthz/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert payload == {"status": "ok"}


class PublicCatalogPayloadTests(TestCase):
    """The catalog item carries what the web app reads, under its names."""

    def test_an_item_publishes_its_price_and_link(self) -> None:
        """The card reads ``price``; a renamed key leaves the site priceless."""
        store = Store.objects.create(
            name="Black Skull",
            display_name="Black Skull",
            scraper_slug="black_skull",
        )
        product = Product.objects.create(
            name="Whey 3W Chocolate",
            brand=Brand.objects.create(name="black-skull", display_name="Black Skull"),
            net_mass=Decimal(900),
            is_published=True,
        )
        ProductNutrition.objects.create(
            product=product,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(12),
            ),
        )
        _link_offer(
            product=product,
            store=store,
            product_link="https://blackskull.example/whey?skuId=1014",
            price=119.90,
        )

        (item,) = json.loads(self.client.get("/api/catalog/products/").content)["items"]

        assert Decimal(item["price"]) == Decimal("119.90"), item
        assert item["externalLink"] == "https://blackskull.example/whey?skuId=1014"
