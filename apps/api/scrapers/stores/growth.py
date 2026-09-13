"""Wap.Store API spider for Growth Supplements."""

import logging

from ..crawler.spiders.wapstore import WapStoreApiSpider

logger = logging.getLogger(__name__)


class GrowthSpider(WapStoreApiSpider):
    """Spider for Growth Supplements (Wap.Store API)."""

    name = "growth"
    BRAND_NAME = "Growth Supplements"
    STORE_SLUG = "growth"
    BASE_URL = "https://www.gsuplementos.com.br"

    API_LISTING = (
        "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category"
    )
    API_MENU = "https://www.gsuplementos.com.br/api/v2/front/struct/menus/nova-home-suplementos-categorias"

    FALLBACK_CATEGORIES = (
        "/proteina/",
        "/creatina/",
        "/aminoacidos/",
        "/pre-treino/",
        "/vitaminas/",
        "/acessorios/",
        "/vegano/",
    )
