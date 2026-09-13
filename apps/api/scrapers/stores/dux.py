"""Nuvemshop storefront spider for Dux Nutrition.

The store migrated off VTEX to Nuvemshop, and the ``www`` host now redirects
to the apex domain.
"""

import logging

from ..crawler.spiders.nuvemshop import NuvemshopSpider

logger = logging.getLogger(__name__)


class DuxSpider(NuvemshopSpider):
    """Spider for Dux Nutrition (Nuvemshop storefront)."""

    name = "dux"
    BRAND_NAME = "Dux Nutrition"
    STORE_SLUG = "dux_nutrition"
    BASE_URL = "https://duxhumanhealth.com"

    FALLBACK_CATEGORIES = ("produtos",)
