"""Application services for merchant offers and price observations."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from .models import Offer, PriceObservation, StockStatus


class OfferListingInput(Protocol):
    """Minimal listing fields required to resolve an offer observation."""

    external_id: str | None
    product_link: str
    price: float
    stock_status: str


class OfferObservationService:
    """Resolve merchant offers and append price observations when needed."""

    def resolve_for_listing(
        self,
        *,
        store_slug: str,
        listing: OfferListingInput,
    ) -> Offer:
        """Resolve or create the offer represented by a product listing payload."""
        price = Decimal(str(listing.price))
        stock_status = self._normalize_stock_status(listing.stock_status)

        offer, _created = Offer.objects.update_or_create(
            store_slug=store_slug,
            external_id=listing.external_id or "",
            defaults={
                "url": listing.product_link,
                "current_price": price,
                "current_stock_status": stock_status,
            },
        )
        self._append_observation_if_changed(offer, price, stock_status)
        return offer

    def _append_observation_if_changed(
        self,
        offer: Offer,
        price: Decimal,
        stock_status: str,
    ) -> None:
        """Append a price observation only when price or stock status changed."""
        latest = offer.price_observations.values("price", "stock_status").first()
        if (
            latest is not None
            and latest["price"] == price
            and latest["stock_status"] == stock_status
        ):
            return

        PriceObservation.objects.create(
            offer=offer,
            price=price,
            stock_status=stock_status,
        )

    def _normalize_stock_status(self, value: str) -> str:
        """Return a supported stock status, defaulting to available."""
        valid = {choice for choice, _label in StockStatus.choices}
        return value if value in valid else StockStatus.AVAILABLE
