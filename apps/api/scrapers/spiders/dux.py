"""Nuvemshop storefront spider for Dux Nutrition.

The store migrated off VTEX to Nuvemshop, and the ``www`` host now redirects
to the apex domain.
"""

import logging

from .nuvemshop_spider import NuvemshopSpider

logger = logging.getLogger(__name__)


class DuxSpider(NuvemshopSpider):
    """Spider for Dux Nutrition (Nuvemshop storefront)."""

    BRAND_NAME = "Dux Nutrition"
    STORE_SLUG = "dux_nutrition"
    BASE_URL = "https://duxhumanhealth.com"

    FALLBACK_CATEGORIES = ("produtos",)
