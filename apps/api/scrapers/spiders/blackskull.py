"""Spider configuration for Black Skull."""

import logging

from .vtex_search_spider import VtexSearchSpider

logger = logging.getLogger(__name__)


class BlackSkullSpider(VtexSearchSpider):
    """Spider for Black Skull (VTEX legacy search API).

    Uses the public VTEX catalog search endpoint instead of the persisted
    GraphQL query: the store rotates its persisted-query SHA256 hash, which
    intermittently breaks GraphQL crawls with ``PersistedQueryNotFound``.
    """

    BRAND_NAME = "Black Skull"
    STORE_SLUG = "black_skull"
    BASE_URL = "https://www.blackskullusa.com.br"

    API_TREE = "https://www.blackskullusa.com.br/api/catalog_system/pub/category/tree/3"

    FALLBACK_CATEGORIES = (
        "proteina",
        "aminoacidos",
        "vitaminas",
        "vestuario",
        "acessorios",
        "kits",
    )
