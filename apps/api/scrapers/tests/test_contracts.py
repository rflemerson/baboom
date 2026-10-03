"""The scraper contracts assume nothing a source did not say."""

from __future__ import annotations

from django.test import SimpleTestCase

from scrapers.contracts import ScrapedItemIngestionInput, StockReading


class ContractDefaultTests(SimpleTestCase):
    """Defaults are unknowns, not optimistic readings."""

    def test_ingestion_without_a_stock_reading_is_unknown(self) -> None:
        """No stock reading is not availability."""
        data = ScrapedItemIngestionInput(store_slug="s", external_id="1")

        assert data.stock_status == StockReading.UNKNOWN
