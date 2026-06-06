"""Application services for merchant offers and price observations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .models import Offer, PriceObservation, StockStatus

logger = logging.getLogger(__name__)


class OfferListingInput(Protocol):
    """Minimal listing fields required to resolve an offer observation."""

    external_id: str | None
    product_link: str
    price: float
    stock_status: str


@dataclass(frozen=True)
class OfferObservationResult:
    """Outcome of recording an offer observation.

    ``changed`` is True when the offer was newly created or its price/stock
    moved since the last observation. Callers (e.g. the weekly HTML enrichment)
    use it to skip unchanged offers.
    """

    offer: Offer
    created: bool
    changed: bool


class OfferObservationService:
    """Resolve merchant offers and append price observations when needed.

    This is the single owner of "upsert an offer and record a price observation
    if it changed". Both the scraper and the catalog listing flow go through it.
    """

    def resolve_for_listing(
        self,
        *,
        store_slug: str,
        listing: OfferListingInput,
    ) -> Offer:
        """Resolve or create the offer represented by a product listing payload."""
        return self.record(
            store_slug=store_slug,
            external_id=listing.external_id or "",
            price=Decimal(str(listing.price)),
            stock_status=listing.stock_status,
            snapshot={"url": listing.product_link},
        ).offer

    def record(
        self,
        *,
        store_slug: str,
        external_id: str,
        price: Decimal | None,
        stock_status: str,
        snapshot: dict[str, object],
    ) -> OfferObservationResult:
        """Upsert the offer with a snapshot and append a price observation.

        ``snapshot`` carries the descriptive fields the caller observed (url and,
        for the scraper, name/category/identifiers). The current price and stock
        status are always refreshed; a new observation is appended only when the
        price or stock status changed. The returned result reports whether the
        offer was created or moved, so callers can act only on real changes.
        """
        normalized_status = StockStatus.normalize(stock_status)
        offer, created = Offer.objects.update_or_create(
            store_slug=store_slug,
            external_id=external_id,
            defaults={
                **snapshot,
                "current_price": price,
                "current_stock_status": normalized_status,
            },
        )
        changed = created
        if price is not None:
            changed = (
                self._append_observation_if_changed(offer, price, normalized_status)
                or created
            )
        return OfferObservationResult(offer=offer, created=created, changed=changed)

    def _append_observation_if_changed(
        self,
        offer: Offer,
        price: Decimal,
        stock_status: str,
    ) -> bool:
        """Append a price observation when price or stock changed; report change."""
        latest = offer.price_observations.values("price", "stock_status").first()
        if (
            latest is not None
            and latest["price"] == price
            and latest["stock_status"] == stock_status
        ):
            return False

        PriceObservation.objects.create(
            offer=offer,
            price=price,
            stock_status=stock_status,
        )
        logger.info("Recorded price observation for %s: R$%s", offer.store_slug, price)
        return True
