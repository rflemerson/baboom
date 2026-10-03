"""Record what a source said as typed, append-only observations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils import timezone

from commerce.models import PaymentMethod

from .models import (
    AvailabilityObservation,
    CollectionCoverage,
    FeaturedOfferObservation,
    ObservationBatch,
    OfferPriceObservation,
    PaymentScope,
)

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal

    from commerce.models import Market

    from .models import ListingVariant, Offer


@dataclass(frozen=True)
class PriceRecord:
    """One value a source stated, with everything that gives it meaning."""

    role: str
    amount: Decimal
    source_field: str
    payment_scope: str = PaymentScope.UNKNOWN
    payment_method: str = ""
    payment_label_raw: str = ""
    payment_provider_raw: str = ""
    installment_count: int | None = None
    installment_amount: Decimal | None = None
    interest: str = "unknown"
    capture_stage: str = "catalog"
    evidence_level: str = "observed_in_catalog"
    composition: str = "unknown"
    included_adjustments: tuple[dict[str, str], ...] = ()
    quantity_min: int = 1
    context: dict[str, object] = field(default_factory=dict)

    def condition_key(self) -> str:
        """Hash the dimensions that identify the condition, never amount or time."""
        dimensions = {
            "role": self.role,
            "source_field": self.source_field,
            "payment_scope": self.payment_scope,
            "payment_method": self.payment_method,
            "payment_label_raw": self.payment_label_raw,
            "payment_provider_raw": self.payment_provider_raw,
            "installment_count": self.installment_count,
            "capture_stage": self.capture_stage,
            "quantity_min": self.quantity_min,
            "context": self.context,
        }
        canonical = json.dumps(dimensions, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class CoverageRecord:
    """How completely one dimension of one partition was read."""

    dimension: str
    partition: str
    status: str
    reason: str = ""


@dataclass(frozen=True)
class _Subject:
    """An offer, or a variant whose price names no seller."""

    offer: Offer | None
    listing_variant: ListingVariant | None

    def filter(self) -> Q:
        """Return the lookup of this subject's observations."""
        if self.offer is not None:
            return Q(offer=self.offer)
        return Q(listing_variant=self.listing_variant)


class ObservationService:
    """Append typed observations; a repeated value adds nothing."""

    def __init__(self) -> None:
        """Cache payment methods per market country for one ingestion."""
        self._methods: dict[tuple[str, str], PaymentMethod | None] = {}

    @staticmethod
    def open_batch(
        market: Market,
        *,
        adapter: str,
        adapter_version: str,
        request_context: dict[str, object] | None = None,
    ) -> ObservationBatch:
        """Start a batch of values read together."""
        return ObservationBatch.objects.create(
            market=market,
            adapter=adapter,
            adapter_version=adapter_version,
            request_context=request_context or {},
        )

    @staticmethod
    def close_batch(batch: ObservationBatch, coverage: list[CoverageRecord]) -> None:
        """Record coverage and close the batch as complete or partial."""
        CollectionCoverage.objects.bulk_create(
            CollectionCoverage(
                batch=batch,
                dimension=item.dimension,
                partition=item.partition,
                status=item.status,
                reason=item.reason,
            )
            for item in coverage
        )
        complete = coverage and all(item.status == "complete" for item in coverage)
        batch.status = (
            ObservationBatch.Status.COMPLETE
            if complete
            else ObservationBatch.Status.PARTIAL
        )
        batch.finished_at = timezone.now()
        batch.save(update_fields=["status", "finished_at", "updated_at"])

    def record_prices(
        self,
        batch: ObservationBatch,
        prices: list[PriceRecord],
        *,
        offer: Offer | None = None,
        listing_variant: ListingVariant | None = None,
        observed_at: datetime | None = None,
    ) -> int:
        """Append each price whose condition changed amount; return how many."""
        moment = observed_at or timezone.now()
        subject = _Subject(offer, listing_variant)
        rows: list[OfferPriceObservation] = []
        for price in prices:
            key = price.condition_key()
            latest = (
                OfferPriceObservation.objects.filter(
                    subject.filter(), condition_key=key
                )
                .order_by("-observed_at", "-pk")
                .values_list("amount", flat=True)
                .first()
            )
            if latest is not None and latest == price.amount:
                continue
            rows.append(self._row(price, key, batch, subject, moment))
        OfferPriceObservation.objects.bulk_create(rows)
        return len(rows)

    def _row(
        self,
        price: PriceRecord,
        key: str,
        batch: ObservationBatch,
        subject: _Subject,
        moment: datetime,
    ) -> OfferPriceObservation:
        """Build one observation row of a price."""
        method = self._method(batch.market, price.payment_method)
        return OfferPriceObservation(
            offer=subject.offer,
            listing_variant=subject.listing_variant,
            batch=batch,
            amount=price.amount,
            currency_id=batch.market.currency_id,
            role=price.role,
            capture_stage=price.capture_stage,
            evidence_level=price.evidence_level,
            payment_scope=price.payment_scope,
            payment_method=method,
            payment_label_raw=price.payment_label_raw,
            payment_provider_raw=price.payment_provider_raw,
            installment_count=price.installment_count,
            installment_amount=price.installment_amount,
            interest=price.interest,
            quantity_min=price.quantity_min,
            condition_key=key,
            context=price.context,
            source_field=price.source_field,
            composition=price.composition,
            included_adjustments=list(price.included_adjustments),
            observed_at=moment,
            recorded_at=timezone.now(),
        )

    def _method(self, market: Market, code: str) -> PaymentMethod | None:
        """Find a payment method by code, in the market's country or global."""
        if not code:
            return None
        cache_key = (market.country, code)
        if cache_key not in self._methods:
            self._methods[cache_key] = (
                PaymentMethod.objects.filter(code=code)
                .filter(Q(country=market.country) | Q(country=""))
                .order_by("-country")
                .first()
            )
        return self._methods[cache_key]

    @staticmethod
    def record_availability(
        batch: ObservationBatch,
        offer: Offer,
        *,
        status: str,
        quantity: int | None,
        source_field: str = "",
    ) -> bool:
        """Append a stock reading when it changed; report whether it did."""
        latest = (
            AvailabilityObservation.objects.filter(offer=offer)
            .order_by("-observed_at", "-pk")
            .values("status", "quantity")
            .first()
        )
        if latest == {"status": status, "quantity": quantity}:
            return False
        AvailabilityObservation.objects.create(
            offer=offer,
            batch=batch,
            status=status,
            quantity=quantity,
            source_field=source_field,
        )
        return True

    @staticmethod
    def record_featured(
        batch: ObservationBatch,
        listing_variant: ListingVariant,
        offer: Offer,
    ) -> None:
        """Note which offer the variant featured, when that changed."""
        latest = (
            FeaturedOfferObservation.objects.filter(listing_variant=listing_variant)
            .order_by("-observed_at", "-pk")
            .values_list("offer_id", flat=True)
            .first()
        )
        if latest != offer.pk:
            FeaturedOfferObservation.objects.create(
                listing_variant=listing_variant,
                offer=offer,
                batch=batch,
            )
