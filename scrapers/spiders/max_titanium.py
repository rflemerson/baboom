import logging

from .vtex_search_spider import VtexSearchSpider

logger = logging.getLogger(__name__)


class MaxTitaniumSpider(VtexSearchSpider):
    BRAND_NAME = "Max Titanium"
    BASE_URL = "https://www.maxtitanium.com.br"
    API_TREE = "https://www.maxtitanium.com.br/api/catalog_system/pub/category/tree/3"
    FALLBACK_CATEGORIES = [
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
    ]
