"""Application services for merchant offers and price observations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import (
    Listing,
    ListingVariant,
    Offer,
    OfferSourceIdentity,
    PriceObservation,
    StockStatus,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from commerce.models import Market, SellerAccount

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OfferObservationResult:
    """Outcome of recording an offer observation.

    ``changed`` is True when the offer was newly created or its price/stock
    moved since the last observation. Callers use it to skip unchanged offers.
    """

    offer: Offer
    created: bool
    changed: bool


class OfferObservationService:
    """Resolve merchant offers and append price observations when needed.

    This is the single owner of "upsert an offer and record a price observation
    if it changed". Only the scraper writes offers; curation links to them.
    """

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


@dataclass(frozen=True)
class ListingRef:
    """A listing as a source publishes it."""

    external_id: str
    url: str = ""
    title: str = ""
    catalog_product_id: str = ""


@dataclass(frozen=True)
class VariantRef:
    """A selectable unit of a listing as a source publishes it."""

    external_id: str
    options: tuple[dict[str, str], ...] = ()
    selection: dict[str, object] | None = None
    gtin: str = ""


@dataclass(frozen=True)
class OfferIdentityRef:
    """Everything that places one offer: where, which unit, who, and its key."""

    market: Market
    listing: ListingRef
    variant: VariantRef
    seller_account: SellerAccount | None
    scheme: str
    key: str


class OfferIdentityService:
    """Place an offer under its listing, variant and seller, and record its names.

    An offer's seller is part of its identity: once known it is never
    overwritten, because a different seller is a different offer. A source that
    starts naming another seller for the same key is logged and left alone.
    """

    LEGACY_SCHEME = "legacy"

    @staticmethod
    def listing(market: Market, listing: ListingRef) -> Listing:
        """Upsert a listing by its id within its market."""
        row, _created = Listing.objects.update_or_create(
            market=market,
            external_id=listing.external_id,
            defaults={
                "url": listing.url,
                "title": listing.title,
                "catalog_product_id": listing.catalog_product_id,
            },
        )
        return row

    def bind(self, offer: Offer, ref: OfferIdentityRef) -> ListingVariant:
        """Upsert the listing and variant, attach the offer, record its keys."""
        market, variant, seller_account = ref.market, ref.variant, ref.seller_account
        listing_row = self.listing(market, ref.listing)
        variant_row, _created = ListingVariant.objects.update_or_create(
            listing=listing_row,
            external_id=variant.external_id,
            defaults={
                "options": list(variant.options),
                "selection": variant.selection or {},
                "gtin": variant.gtin,
            },
        )
        updates: list[str] = []
        if offer.listing_variant_id != variant_row.pk:
            offer.listing_variant = variant_row
            updates.append("listing_variant")
        if seller_account is not None:
            if offer.seller_account_id is None:
                offer.seller_account = seller_account
                updates.append("seller_account")
            elif offer.seller_account_id != seller_account.pk:
                logger.warning(
                    "Offer %s is sold by account %s; the source now names %s",
                    offer.pk,
                    offer.seller_account_id,
                    seller_account.pk,
                )
        if updates:
            offer.save(update_fields=[*updates, "updated_at"])
        self._identify(offer, market.namespace, self.LEGACY_SCHEME, offer.external_id)
        self._identify(offer, market.namespace, ref.scheme, ref.key)
        return variant_row

    @staticmethod
    def _identify(offer: Offer, namespace: str, scheme: str, key: str) -> None:
        """Record one name of the offer; a name never moves to another offer."""
        identity, created = OfferSourceIdentity.objects.get_or_create(
            namespace=namespace,
            scheme=scheme,
            scheme_version=1,
            key=key,
            defaults={"offer": offer},
        )
        if not created and identity.offer_id != offer.pk:
            logger.warning(
                "Key %s is already offer %s, not %s",
                identity,
                identity.offer_id,
                offer.pk,
            )
