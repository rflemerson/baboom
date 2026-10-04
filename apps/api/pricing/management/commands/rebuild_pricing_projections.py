"""Preview or rebuild disposable public projections without changing facts."""

from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand

from pricing.projections import ProjectionService

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    """Make schema transitions explicit, preview-first and repeatable."""

    help = (
        "Preview public projection rebuild; --apply evaluates and replaces projections."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Require an explicit apply flag for writes."""
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args: object, **options: object) -> None:
        """Report the expected scope before any writes."""
        _ = args
        service = ProjectionService()
        ids = service.linked_offers()
        policies = service.policies()
        self.stdout.write(
            f"Linked offers: {len(ids)}; public policies: {len(policies)}"
        )
        if options["apply"]:
            count = service.refresh(ids)
            self.stdout.write(f"Rebuilt projections: {count}")
        else:
            self.stdout.write(
                "Preview only; observations, quotes and links are unchanged."
            )
