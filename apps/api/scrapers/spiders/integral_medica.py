"""Shopify API spider for Integralmedica.

The store migrated off VTEX; the customer-facing domain is now a headless
storefront whose product routes do not resolve, so the canonical Shopify
domain is the one that serves both the catalog API and fetchable product
pages for the review pipeline.
"""

import logging

from .shopify_api_spider import ShopifyApiSpider

logger = logging.getLogger(__name__)


class IntegralMedicaSpider(ShopifyApiSpider):
    """Spider for Integralmedica (Shopify API)."""

    BRAND_NAME = "Integralmedica"
    STORE_SLUG = "integral_medica"
    BASE_URL = "https://totvsibi-integralmedica-dc.myshopify.com"

    FALLBACK_CATEGORIES = (
        "colecao-proteinas",
        "colecao-whey-protein-concentrado",
        "colecao-nutri-whey",
        "creatina",
        "colecao-creatina",
        "aminoacidos",
        "aminoacidos-essenciais",
        "hipercalorico",
        "barra-de-proteina",
        "proteina",
        "proteina-de-carne",
        "acessorios",
    )

    USE_PRODUCT_DETAIL = False
    PRICE_INT_IS_CENTS = False
    PRICE_DIGIT_STR_IS_CENTS = False
