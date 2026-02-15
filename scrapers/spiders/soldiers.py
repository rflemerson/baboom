import logging

from .shopify_api_spider import ShopifyApiSpider

logger = logging.getLogger(__name__)


class SoldiersSpider(ShopifyApiSpider):
    """Spider for Soldiers Nutrition (Shopify public API)."""

    BRAND_NAME = "Soldiers Nutrition"
    STORE_SLUG = "soldiers_nutrition"
    BASE_URL = "https://soldiersnutrition.com.br"

    FALLBACK_CATEGORIES = [
        "creatina",
        "whey-protein-soldiers",
        "glutamina",
        "pre-treino",
        "vitaminas-e-minerais",
        "acessorios",
    ]

    USE_PRODUCT_DETAIL = True
    PRICE_INT_IS_CENTS = True
    PRICE_DIGIT_STR_IS_CENTS = True
