import logging

from .shopify_api_spider import ShopifyApiSpider

logger = logging.getLogger(__name__)


class DarkLabSpider(ShopifyApiSpider):
    """Spider for Dark Lab (Shopify API)."""

    BRAND_NAME = "Dark Lab"
    STORE_SLUG = "dark_lab"
    BASE_URL = "https://www.darklabsuplementos.com.br"

    FALLBACK_CATEGORIES = [
        "best-sellers",
        "whey-protein",
        "creatina",
        "pre-treino",
        "hipercalorico",
        "aminoacidos",
        "acessorios",
        "kits",
        "vegan",
        "vitaminas",
    ]

    USE_PRODUCT_DETAIL = False
    PRICE_INT_IS_CENTS = False
    PRICE_DIGIT_STR_IS_CENTS = False
