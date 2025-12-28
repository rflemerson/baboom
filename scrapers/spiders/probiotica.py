import logging

from .vtex_search_spider import VtexSearchSpider

logger = logging.getLogger(__name__)


class ProbioticaSpider(VtexSearchSpider):
    BRAND_NAME = "Probiótica"
    BASE_URL = "https://www.probiotica.com.br"
    # Dynamic Category Tree API
    API_TREE = "https://www.probiotica.com.br/api/catalog_system/pub/category/tree/3"

    # Fallback categories if tree fails
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
