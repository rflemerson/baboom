"""What each adapter can read, declared, versioned, and checked by tests.

A capability is a claim about a source and its context, not about a whole
platform: a store on a known platform may still hide sellers or payment
prices. Rankings and coverage use these claims; nothing else branches on a
store or a platform name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Support = Literal["complete", "partial", "none"]


@dataclass(frozen=True)
class AdapterCapabilities:
    """What one adapter version reads from its source."""

    version: str
    variants: Support
    sellers: Literal["channel_owner_only", "named", "none"]
    payment_prices: Support
    cart_quote: Support
    destination_delivery: Support
    rewards: Support
    selectable_route: Literal["variant", "variant_and_seller", "page_only"]
    access: Literal["public", "authorized"] = "public"


# Per provider: the most a source tolerates from one IP and account. Scrapy
# applies them to every spider of the provider, so adding the Nth store of a
# platform does not multiply the load on it.
PROVIDER_LIMITS: dict[str, dict[str, float | int]] = {
    "shopify": {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.5},
    "vtex": {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.5},
    "wapstore": {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.5},
    "nuvemshop": {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0},
}
