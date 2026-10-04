"""Every adapter declares what it reads; nothing branches on a store's name."""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase
from scrapy.settings import Settings
from scrapy.spiderloader import SpiderLoader
from scrapy.utils.project import get_project_settings

from scrapers.capabilities import PROVIDER_LIMITS, AdapterCapabilities
from scrapers.stores.dark_lab import DarkLabSpider

ROOT = Path(__file__).resolve().parents[2]
STORE_OR_PLATFORM = re.compile(
    r"\bgrowth\b|black.?skull|max.?titanium|probi[oó]tica|\bdux\b|dark.?lab"
    r"|integral.?m[eé]dica|soldiers|\bvtex\b|shopify|wap.?store|nuvemshop"
    r"|amazon|mercado.?livre",
    re.IGNORECASE,
)


def _spiders() -> list[type]:
    settings = get_project_settings()
    settings.setmodule("scrapers.crawler.settings")
    loader = SpiderLoader.from_settings(settings)
    return [loader.load(name) for name in loader.list()]


class CapabilityTests(SimpleTestCase):
    """Capabilities are declared per adapter and applied per provider."""

    def test_every_registered_spider_declares_its_capabilities(self) -> None:
        """No adapter reaches ingestion without saying what it reads."""
        for spider in _spiders():
            normalizer = getattr(spider, "normalizer", None)
            if normalizer is None:
                continue
            with self.subTest(spider.name):
                assert isinstance(normalizer.capabilities, AdapterCapabilities)
                assert normalizer.provider in PROVIDER_LIMITS

    def test_provider_limits_apply_to_every_store_of_the_platform(self) -> None:
        """Adding a Shopify store does not add Shopify load per store."""
        settings = Settings()
        DarkLabSpider.update_settings(settings)

        assert (
            settings.getint("CONCURRENT_REQUESTS_PER_DOMAIN")
            == (PROVIDER_LIMITS["shopify"]["CONCURRENT_REQUESTS_PER_DOMAIN"])
        )

    def test_the_engine_and_ranking_never_name_a_store_or_platform(self) -> None:
        """Commercial decisions are data, not branches on names."""
        paths = [
            *(ROOT / "pricing" / "domain").glob("*.py"),
            ROOT / "pricing" / "selectors.py",
            ROOT / "pricing" / "projections.py",
            ROOT / "core" / "selectors.py",
        ]
        for path in paths:
            with self.subTest(path.name):
                assert not STORE_OR_PLATFORM.search(path.read_text(encoding="utf-8"))
