import logging

from .vtex_search_spider import VtexSearchSpider

logger = logging.getLogger(__name__)


class ProbioticaSpider(VtexSearchSpider):
    """Spider for Probiotica."""

    BRAND_NAME = "Probiotica"
    STORE_SLUG = "probiotica"
    BASE_URL = "https://www.probiotica.com.br"
    API_TREE = "https://www.probiotica.com.br/api/catalog_system/pub/category/tree/3"
    FALLBACK_CATEGORIES = [
        "whey-protein",
        "proteinas",
        "creatina",
        "aminoacidos",
        "pre-treino",
        "massas",
        "emagrecimento",
        "barras",
        "vegan",
        "kit",
    ]
