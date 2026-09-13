"""VTEX search spider for Max Titanium."""

import logging

from ..crawler.spiders.vtex_search import VtexSearchSpider

logger = logging.getLogger(__name__)


class MaxTitaniumSpider(VtexSearchSpider):
    """Spider for Max Titanium."""

    name = "max_titanium"
    BRAND_NAME = "Max Titanium"
    STORE_SLUG = "max_titanium"
    BASE_URL = "https://www.maxtitanium.com.br"
    API_TREE = "https://www.maxtitanium.com.br/api/catalog_system/pub/category/tree/3"
    FALLBACK_CATEGORIES = (
        "whey-protein",
        "proteinas",
        "creatina",
        "aminoacidos",
        "pre-treino",
        "massas",
        "emagrecimento",
        "barras-de-proteina",
        "proteina-vegana",
        "albumina",
        "paginas-especiais",
    )
