import logging

from .vtex_search_spider import VtexSearchSpider

logger = logging.getLogger(__name__)


class IntegralMedicaSpider(VtexSearchSpider):
    BRAND_NAME = "Integralmedica"
    BASE_URL = "https://www.integralmedica.com.br"
    API_TREE = (
        "https://www.integralmedica.com.br/api/catalog_system/pub/category/tree/3"
    )

    # Fallback categories if tree fails
    FALLBACK_CATEGORIES = [
        "proteina",
        "creatina",
        "aminoacidos",
        "massa-muscular",
        "energia",
        "emagrecimento",
    ]
