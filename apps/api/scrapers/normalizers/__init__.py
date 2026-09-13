"""Pure transformations from store payloads to scraper contracts."""

import logging

from .nuvemshop import NuvemshopNormalizer
from .shopify import ShopifyNormalizer
from .vtex import VtexNormalizer
from .wapstore import WapStoreNormalizer

__all__ = (
    "NuvemshopNormalizer",
    "ShopifyNormalizer",
    "VtexNormalizer",
    "WapStoreNormalizer",
)

logger = logging.getLogger(__name__)
