"""Compare a market's current prices with its projections before switching it.

Reads only. For each public policy, lists the products the catalog prices
today that projections would leave without a price, grouped by store and by
the reason the projection gives.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.selectors import current_prices, public_catalog_products
from pricing.models import OfferScenarioProjection
from pricing.projections import ProjectionService
from pricing.selectors import projected_prices

if TYPE_CHECKING:
    from argparse import ArgumentParser

    from core.selectors import PriceSource
    from pricing.models import PricingPolicyRevision


class Command(BaseCommand):
    """Report what a market would lose by reading projections now."""

    help = "Report products priced today that projections leave without a price."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Choose the market and how much detail to print."""
        parser.add_argument("--country", default="BR")
        parser.add_argument("--currency", default="BRL")
        parser.add_argument(
            "--details",
            action="store_true",
            help="List every product that loses its price.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Print, per policy, priced counts and the losses by store and reason."""
        _ = args
        country, currency = str(options["country"]), str(options["currency"])
        today = self._priced(current_prices(country, currency))
        self.stdout.write(f"Priced today in {country}/{currency}: {len(today)}")
        for policy in ProjectionService.policies():
            source = projected_prices(
                policy,
                timezone.now(),
                country=country,
                currency=currency,
            )
            projected = self._priced(source)
            lost = {pk: name for pk, name in today.items() if pk not in projected}
            self.stdout.write(
                f"Policy {policy.key}: {len(projected)} priced, "
                f"{len(lost)} priced today lose their price",
            )
            reasons = self._reasons(policy, lost)
            for label, counts in (
                ("store", Counter(store for store, _reason in reasons.values())),
                ("reason", Counter(reason for _store, reason in reasons.values())),
            ):
                for key, count in counts.most_common():
                    self.stdout.write(f"  by {label}: {key}: {count}")
            if options["details"]:
                for pk, name in sorted(lost.items(), key=lambda item: item[1]):
                    store, reason = reasons[pk]
                    self.stdout.write(f"  {name} [{store}]: {reason}")

    @staticmethod
    def _priced(source: PriceSource) -> dict[int, str]:
        """Return the published products this source gives a price."""
        rows = public_catalog_products(source).filter(price__isnull=False)
        return dict(rows.values_list("pk", "name"))

    @staticmethod
    def _reasons(
        policy: PricingPolicyRevision,
        lost: dict[int, str],
    ) -> dict[int, tuple[str, str]]:
        """Name, per product, a store and why its projection has no price."""
        found: dict[int, tuple[str, str]] = {}
        rows = OfferScenarioProjection.objects.filter(
            policy=policy,
            alternative="best",
            offer__product_store__product__in=lost,
        ).values_list(
            "offer__product_store__product",
            "offer__store_slug",
            "status",
            "expires_at",
            "explanation",
        )
        now = timezone.now()
        for product_id, store, status, expires_at, explanation in rows:
            refusals = (explanation or {}).get("refusals") or []
            if status == OfferScenarioProjection.Status.PRICED:
                reason = "expired" if expires_at and expires_at <= now else "other"
            elif refusals:
                reason = str(refusals[0]).split(": ", 1)[-1]
            else:
                reason = str(status)
            found.setdefault(product_id, (store, reason))
        for pk in lost:
            found.setdefault(pk, ("-", "no projection"))
        return found
