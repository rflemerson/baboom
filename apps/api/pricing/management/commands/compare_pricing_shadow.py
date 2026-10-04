"""Compare the legacy catalog with a policy's projections, product by product.

Run before adding a country to ``PRICING_PROJECTION_COUNTRIES``. It reads only.
For every published product of one market it compares the legacy price, link
and offer with the projected ones, and names what differs: the amount, the
offer, and through the offer the seller and the variant. A difference is
investigated at its cause, never forced away.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.selectors import legacy_prices, public_catalog_products
from offers.models import Offer
from pricing.selectors import projected_prices, public_policy

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from decimal import Decimal

    from core.models import Product


@dataclass(frozen=True)
class Side:
    """What one source shows for a product."""

    amount: Decimal | None
    link: str | None
    offer_id: int | None


@dataclass(frozen=True)
class Difference:
    """One product shown differently by the two sources."""

    product_id: int
    name: str
    legacy: Side
    projected: Side
    kinds: tuple[str, ...]


def _side(row: Product | None) -> Side:
    if row is None:
        return Side(None, None, None)
    return Side(row.price, row.external_link, row.price_offer_id)


def _money(value: Decimal | None) -> str:
    """Show an amount in cents, or a dash."""
    return "-" if value is None else f"{value:.2f}"


def _kinds(legacy: Side, projected: Side, offers: dict[int, Offer]) -> list[str]:
    """Name every way two sides differ."""
    kinds: list[str] = []
    if legacy.amount is None and projected.amount is not None:
        kinds.append("only projected")
    elif projected.amount is None and legacy.amount is not None:
        kinds.append("only legacy")
    elif legacy.amount != projected.amount:
        kinds.append("amount")
    if legacy.offer_id != projected.offer_id and None not in (
        legacy.offer_id,
        projected.offer_id,
    ):
        kinds.append("offer")
        old, new = offers.get(legacy.offer_id), offers.get(projected.offer_id)
        if old and new and old.seller_account_id != new.seller_account_id:
            kinds.append("seller")
        if old and new and old.listing_variant_id != new.listing_variant_id:
            kinds.append("variant")
    if legacy.link != projected.link:
        kinds.append("link")
    return kinds


class Command(BaseCommand):
    """Report every product whose projected offer, price or link differs."""

    help = (
        "Compare, read only, legacy catalog prices with a policy's projections "
        "in one market. With --strict, any difference exits with status 1."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Choose the policy, the market and whether a difference fails."""
        parser.add_argument(
            "--policy", default=None, help="Policy key; default if omitted."
        )
        parser.add_argument("--country", default=settings.CATALOG_DEFAULT_COUNTRY)
        parser.add_argument("--currency", default=settings.CATALOG_DEFAULT_CURRENCY)
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *_args: object, **options: object) -> None:
        """Print the summary and the first differences."""
        policy = public_policy(str(options["policy"]) if options["policy"] else None)
        if policy is None:
            msg = "No published policy with that key."
            raise CommandError(msg)
        country, currency = str(options["country"]), str(options["currency"])
        legacy = {
            row.pk: row
            for row in public_catalog_products(
                price_source=legacy_prices(country, currency),
            )
        }
        projected = {
            row.pk: row
            for row in public_catalog_products(
                price_source=projected_prices(
                    policy,
                    timezone.now(),
                    country=country,
                    currency=currency,
                ),
            )
        }
        offer_ids = {
            row.price_offer_id for row in (*legacy.values(), *projected.values())
        }
        offers = Offer.objects.in_bulk([pk for pk in offer_ids if pk is not None])
        differences = []
        for pk, row in legacy.items():
            old, new = _side(row), _side(projected.get(pk))
            kinds = _kinds(old, new, offers)
            if kinds:
                differences.append(Difference(pk, row.name, old, new, tuple(kinds)))
        self.stdout.write(
            f"Policy {policy} in {country}/{currency}: {len(legacy)} products, "
            f"{len(legacy) - len(differences)} equal, {len(differences)} different.",
        )
        counts: dict[str, int] = {}
        for difference in differences:
            for kind in difference.kinds:
                counts[kind] = counts.get(kind, 0) + 1
        for kind, count in sorted(counts.items()):
            self.stdout.write(f"  {kind}: {count}")
        for difference in differences[: int(options["limit"])]:
            self.stdout.write(
                f"  #{difference.product_id} {difference.name}: "
                f"{_money(difference.legacy.amount)} -> "
                f"{_money(difference.projected.amount)} "
                f"({', '.join(difference.kinds)})",
            )
        if differences and options["strict"]:
            msg = f"{len(differences)} products differ."
            raise CommandError(msg, returncode=1)
