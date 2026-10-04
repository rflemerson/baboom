"""Compare the legacy catalog price with the projected one, product by product.

Run before switching ``PRICING_READ_PROJECTIONS`` on. It reads only: every
published product's legacy price and link next to the projection of a policy,
and reports each difference with its reason. A difference is investigated,
never forced away.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.selectors import public_catalog_products
from pricing.selectors import projected_prices, public_policy

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from decimal import Decimal


@dataclass(frozen=True)
class Difference:
    """One product priced differently by the two sources."""

    product_id: int
    name: str
    legacy: Decimal | None
    projected: Decimal | None
    legacy_link: str | None
    projected_link: str | None

    @property
    def kind(self) -> str:
        """Classify the difference."""
        if self.legacy is None:
            return "only projected"
        if self.projected is None:
            return "only legacy"
        if self.legacy != self.projected:
            return "amount"
        return "link"


def _money(value: Decimal | None) -> str:
    """Show an amount in cents, or a dash."""
    return "-" if value is None else f"{value:.2f}"


class Command(BaseCommand):
    """Report every product whose projected price or link differs from legacy."""

    help = (
        "Compare legacy catalog prices with a policy's projections, read only. "
        "Exit status 1 with --strict when any product differs."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Choose the policy and whether a difference fails the command."""
        parser.add_argument(
            "--policy", default=None, help="Policy key; default policy if omitted."
        )
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *_args: object, **options: object) -> None:
        """Print the summary and the first differences."""
        policy = public_policy(str(options["policy"]) if options["policy"] else None)
        if policy is None:
            msg = "No published policy with that key."
            raise CommandError(msg)
        legacy = {row.pk: row for row in public_catalog_products()}
        projected = {
            row.pk: row
            for row in public_catalog_products(
                price_source=projected_prices(policy, timezone.now()),
            )
        }
        differences = [
            Difference(
                product_id=pk,
                name=row.name,
                legacy=row.price,
                projected=projected[pk].price if pk in projected else None,
                legacy_link=row.external_link,
                projected_link=projected[pk].external_link if pk in projected else None,
            )
            for pk, row in legacy.items()
            if pk not in projected
            or row.price != projected[pk].price
            or row.external_link != projected[pk].external_link
        ]
        self.stdout.write(
            f"Policy {policy}: {len(legacy)} products, "
            f"{len(legacy) - len(differences)} equal, {len(differences)} different.",
        )
        counts: dict[str, int] = {}
        for difference in differences:
            counts[difference.kind] = counts.get(difference.kind, 0) + 1
        for kind, count in sorted(counts.items()):
            self.stdout.write(f"  {kind}: {count}")
        for difference in differences[: int(options["limit"])]:
            self.stdout.write(
                f"  #{difference.product_id} {difference.name}: "
                f"{_money(difference.legacy)} -> {_money(difference.projected)} "
                f"({difference.kind})",
            )
        if differences and options["strict"]:
            msg = f"{len(differences)} products differ."
            raise CommandError(msg, returncode=1)
