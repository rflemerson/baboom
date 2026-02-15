import logging

from .vtex_graphql_spider import VtexGraphqlSpider

logger = logging.getLogger(__name__)


class BlackSkullSpider(VtexGraphqlSpider):
    """Spider for Black Skull (VTEX GraphQL)."""

    BRAND_NAME = "Black Skull"
    STORE_SLUG = "black_skull"
    BASE_URL = "https://www.blackskullusa.com.br"

    API_ENDPOINT = "https://www.blackskullusa.com.br/_v/segment/graphql/v1"
    API_TREE = "https://www.blackskullusa.com.br/api/catalog_system/pub/category/tree/3"
    QUERY_HASH = "ee2478d319404f621c3e0426e79eba3997665d48cb277a53bf0c3276e8e53c22"

    FALLBACK_CATEGORIES = [
        "proteina",
        "aminoacidos",
        "vitaminas",
        "vestuario",
        "acessorios",
        "kits",
    ]
