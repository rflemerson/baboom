"""VTEX search spider for Integralmedica."""

import logging

from .vtex_search_spider import VtexSearchSpider

logger = logging.getLogger(__name__)


class IntegralMedicaSpider(VtexSearchSpider):
    """Spider for IntegralMedica."""

    BRAND_NAME = "Integralmedica"
    STORE_SLUG = "integral_medica"
    BASE_URL = "https://www.integralmedica.com.br"
    API_TREE = (
        "https://www.integralmedica.com.br/api/catalog_system/pub/category/tree/3"
    )
    FALLBACK_CATEGORIES = (
        "proteina",
        "creatina",
        "aminoacidos",
        "massa-muscular",
        "energia",
        "emagrecimento",
    )
