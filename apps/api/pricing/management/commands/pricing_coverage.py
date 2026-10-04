"""Compare a market's current prices with its projections before switching it.

Reads only. For each public policy, lists the products the catalog prices
today that projections would leave without a price, grouped by store and by
the reason the projection gives for the offer that wins today's price. It also
compares, per product, today's winning offer and link with the ``normal``
projection's. With ``--fail-on-loss`` a lost price is a failure.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.selectors import current_prices, public_catalog_products
from offers.models import Offer
from pricing.models import OfferScenarioProjection
from pricing.projections import ProjectionService
from pricing.selectors import projected_prices, public_policy

if TYPE_CHECKING:
    from argparse import ArgumentParser

    from core.selectors import PriceSource
    from pricing.models import PricingPolicyRevision

# A priced product: its name, the offer that wins and the link it opens.
Priced = tuple[str, int | None, str | None]


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
        parser.add_argument(
            "--fail-on-loss",
            action="store_true",
            help="Exit with an error when any product loses its price.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Print, per policy, priced counts and the losses by store and reason."""
        _ = args
        country, currency = str(options["country"]), str(options["currency"])
        today = self._priced(current_prices(country, currency))
        self.stdout.write(f"Priced today in {country}/{currency}: {len(today)}")
        losses = 0
        for policy in ProjectionService.policies():
            projected = self._priced(self._source(policy, country, currency))
            lost = {pk: price for pk, price in today.items() if pk not in projected}
            losses += len(lost)
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
                for pk, (name, _offer, _link) in sorted(
                    lost.items(), key=lambda item: item[1][0]
                ):
                    store, reason = reasons[pk]
                    self.stdout.write(f"  {name} [{store}]: {reason}")
        self._divergences(today, country, currency)
        if options["fail_on_loss"] and losses:
            msg = f"{losses} price(s) lost by projections; the market is not ready."
            raise CommandError(msg)

    @staticmethod
    def _source(
        policy: PricingPolicyRevision, country: str, currency: str
    ) -> PriceSource:
        return projected_prices(
            policy,
            timezone.now(),
            country=country,
            currency=currency,
        )

    @staticmethod
    def _priced(source: PriceSource) -> dict[int, Priced]:
        """Return the published products this source gives a price."""
        rows = public_catalog_products(source).filter(price__isnull=False)
        return {
            pk: (name, offer_id, link)
            for pk, name, offer_id, link in rows.values_list(
                "pk", "name", "price_offer_id", "external_link"
            )
        }

    def _divergences(
        self, today: dict[int, Priced], country: str, currency: str
    ) -> None:
        """Report products whose winning offer or link differs from ``normal``'s."""
        normal = public_policy("normal")
        if normal is None:
            return
        projected = self._priced(self._source(normal, country, currency))
        found = [
            (name, offer, link, projected[pk][1], projected[pk][2])
            for pk, (name, offer, link) in sorted(
                today.items(), key=lambda item: item[1][0]
            )
            if pk in projected and projected[pk][1:] != (offer, link)
        ]
        self.stdout.write(f"Divergences from the normal projection: {len(found)}")
        for name, offer, link, projected_offer, projected_link in found:
            if offer != projected_offer:
                self.stdout.write(
                    f"  {name}: offer {offer} wins today, {projected_offer} projected"
                )
            if link != projected_link:
                self.stdout.write(
                    f"  {name}: link {link} today, {projected_link} projected"
                )

    @staticmethod
    def _reasons(
        policy: PricingPolicyRevision,
        lost: dict[int, Priced],
    ) -> dict[int, tuple[str, str]]:
        """Name, per product, the winning offer's store and why it has no price.

        The offer is the one that wins today's price, so the reason of a
        product with several linked offers never depends on row order.
        """
        winners = {offer for _name, offer, _link in lost.values() if offer}
        stores = dict(
            Offer.objects.filter(pk__in=winners).values_list("pk", "store_slug"),
        )
        projections = {
            offer_id: (status, expires_at, explanation)
            for offer_id, status, expires_at, explanation in (
                OfferScenarioProjection.objects.filter(
                    policy=policy,
                    alternative="best",
                    offer_id__in=winners,
                ).values_list("offer_id", "status", "expires_at", "explanation")
            )
        }
        now = timezone.now()
        found: dict[int, tuple[str, str]] = {}
        for pk, (_name, offer, _link) in lost.items():
            store = stores.get(offer, "-")
            if offer not in projections:
                found[pk] = (store, "no projection")
                continue
            status, expires_at, explanation = projections[offer]
            refusals = (explanation or {}).get("refusals") or []
            if status == OfferScenarioProjection.Status.PRICED:
                reason = "expired" if expires_at and expires_at <= now else "other"
            elif refusals:
                reason = str(refusals[0]).split(": ", 1)[-1]
            else:
                reason = str(status)
            found[pk] = (store, reason)
        return found
