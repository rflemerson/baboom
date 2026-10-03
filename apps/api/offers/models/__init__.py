"""Offer layer: what stores and marketplaces sell, and what they charge.

``offers`` depends only on ``common`` and ``commerce``. It is written by
``scrapers`` and read by ``core``, ``promotions`` and ``pricing``, and never
imports any of them: a store is known here by its market namespace and the
seller account that sells, never by the curated catalog.
"""

from .identity import (
    FeaturedOfferObservation,
    Listing,
    ListingVariant,
    OfferSourceIdentity,
)
from .observations import (
    AvailabilityObservation,
    CaptureStage,
    CollectionCoverage,
    Evidence,
    EvidenceLevel,
    ObservationBatch,
    OfferPriceObservation,
    PaymentScope,
    PriceRole,
    Tristate,
)
from .offer import (
    FLAVOR_OPTION_PREFIXES,
    DelistReason,
    ItemCondition,
    Offer,
    PriceObservation,
    StockStatus,
    fold,
)

__all__ = [
    "FLAVOR_OPTION_PREFIXES",
    "AvailabilityObservation",
    "CaptureStage",
    "CollectionCoverage",
    "DelistReason",
    "Evidence",
    "EvidenceLevel",
    "FeaturedOfferObservation",
    "ItemCondition",
    "Listing",
    "ListingVariant",
    "ObservationBatch",
    "Offer",
    "OfferPriceObservation",
    "OfferSourceIdentity",
    "PaymentScope",
    "PriceObservation",
    "PriceRole",
    "StockStatus",
    "Tristate",
    "fold",
]
