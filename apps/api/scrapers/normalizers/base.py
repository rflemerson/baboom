"""Protocol implemented by store payload normalizers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..contracts import ScrapedProductInput

logger = logging.getLogger(__name__)


class ProductNormalizer(Protocol):
    """Convert one raw store product into a persistence-ready product."""

    provider: str

    def normalize(
        self,
        raw: dict,
        *,
        store_slug: str,
        base_url: str,
        category: str,
    ) -> ScrapedProductInput | None:
        """Return a normalized product, or None when it cannot be used."""
