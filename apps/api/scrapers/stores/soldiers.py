"""Shopify API spider for Soldiers Nutrition."""

import logging

from ..crawler.spiders.shopify import ShopifyApiSpider
from ..normalizers.shopify import ShopifyNormalizer

logger = logging.getLogger(__name__)


class SoldiersSpider(ShopifyApiSpider):
    """Spider for Soldiers Nutrition (Shopify public API)."""

    name = "soldiers"
    BRAND_NAME = "Soldiers Nutrition"
    STORE_SLUG = "soldiers_nutrition"
    BASE_URL = "https://soldiersnutrition.com.br"

    FALLBACK_CATEGORIES = (
        "creatina",
        "whey-protein-soldiers",
        "glutamina",
        "pre-treino",
        "vitaminas-e-minerais",
        "acessorios",
    )

    USE_PRODUCT_DETAIL = True
    normalizer = ShopifyNormalizer(
        price_int_is_cents=True,
        price_digit_str_is_cents=True,
    )
