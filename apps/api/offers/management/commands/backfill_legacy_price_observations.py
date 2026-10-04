"""Preview or copy the legacy price history into typed observations.

Each legacy row becomes a payable observation whose meaning is
``legacy_unknown``: no payment method, installment, code or composition is
inferred. The currency is the market's, known by its source contract. An offer
without a market (identity not backfilled yet) is reported and skipped.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand
from django.db import transaction

from offers.models import (
    OfferPriceObservation,
    PriceObservation,
    PriceRole,
)
from offers.observations import PriceRecord

if TYPE_CHECKING:
    from argparse import ArgumentParser

LEGACY_SOURCE_FIELD = "legacy.PriceObservation.price"
LEGACY_KEY = PriceRecord(
    role=PriceRole.PAYABLE,
    amount=Decimal(0),
    source_field=LEGACY_SOURCE_FIELD,
).condition_key()


class Command(BaseCommand):
    """Copy legacy price history without inventing its meaning."""

    help = (
        "Preview, or with --apply write, a legacy_unknown typed observation for "
        "each legacy price observation not copied yet."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Preview by default."""
        parser.add_argument("--apply", action="store_true")

    def handle(self, *_args: object, **options: object) -> None:
        """Copy, or count what would be copied."""
        copied = skipped = 0
        legacy = PriceObservation.objects.select_related(
            "offer__listing_variant__listing__market",
        ).order_by("pk")
        with transaction.atomic():
            for row in legacy.iterator():
                variant = row.offer.listing_variant
                if variant is None:
                    skipped += 1
                    continue
                market = variant.listing.market
                _created = OfferPriceObservation.objects.get_or_create(
                    offer=row.offer,
                    condition_key=LEGACY_KEY,
                    observed_at=row.observed_at,
                    defaults={
                        "amount": row.price,
                        "currency_id": market.currency_id,
                        "role": PriceRole.PAYABLE,
                        "semantics": OfferPriceObservation.Semantics.LEGACY_UNKNOWN,
                        "source_field": LEGACY_SOURCE_FIELD,
                        "recorded_at": row.created_at,
                        # Confirmed when it was observed: a migration is not
                        # a new reading of the store.
                        "confirmed_at": row.observed_at,
                    },
                )[1]
                copied += int(_created)
            if not options["apply"]:
                transaction.set_rollback(True)
        verb = "Copied" if options["apply"] else "Would copy"
        self.stdout.write(f"{verb} {copied} observations.")
        self.stdout.write(f"Skipped, offer without a market: {skipped}")
