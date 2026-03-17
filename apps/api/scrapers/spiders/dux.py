"""VTEX search spider for Dux Nutrition."""

import logging

from .vtex_search_spider import VtexSearchSpider

logger = logging.getLogger(__name__)


class DuxSpider(VtexSearchSpider):
    """Spider for Dux Nutrition."""

    BRAND_NAME = "Dux Nutrition"
    STORE_SLUG = "dux_nutrition"
    BASE_URL = "https://www.duxhumanhealth.com"
    API_TREE = "https://www.duxhumanhealth.com/api/catalog_system/pub/category/tree/3"
    FALLBACK_CATEGORIES = (
        "proteinas",
        "creatina",
        "saude",
        "vestuario",
        "acessorios",
        "barras",
        "vegan",
    )
