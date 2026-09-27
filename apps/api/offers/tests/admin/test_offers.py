"""What a curator finds when listing offers through the admin API."""

from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from offers.models import Offer


class OfferListTests(TestCase):
    """An agent narrows offers to one store and reads their flavors."""

    URL = "/admin-api/api/v1/offers/offer/"

    def setUp(self) -> None:
        """Capture the same whey at two stores, in two flavors."""
        user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        for store, flavor, external_id in (
            ("growth", "Natural", "185-4"),
            ("dux_nutrition", "Neutro", "410713044"),
        ):
            Offer.objects.create(
                store_slug=store,
                external_id=external_id,
                name="Whey Protein Concentrado",
                current_price=Decimal("194.33"),
                options=[{"name": "Sabor", "value": flavor}],
            )

    def _rows(self, query: str) -> str:
        """Return the listed rows of a search, as text."""
        response = self.client.get(self.URL, {"q": query})
        return json.dumps(json.loads(response.content)["results"], ensure_ascii=False)

    def test_naming_the_store_in_the_search_narrows_to_it(self) -> None:
        """The list exposes no store filter, so the search has to carry it."""
        rows = self._rows("growth whey")

        assert "growth" in rows
        assert "dux_nutrition" not in rows

    def test_each_row_shows_the_flavor_it_sells(self) -> None:
        """Offers sharing one name are told apart without opening each."""
        assert "Natural" in self._rows("growth whey")
