"""Run the on-demand HTML enrichment pass over scraped pages."""

from typing import TYPE_CHECKING, cast

from django.core.management.base import BaseCommand, CommandError

from scrapers.services import ScraperService

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    """Refresh product-page HTML structured data on demand.

    Examples:
        python manage.py enrich_pages
        python manage.py enrich_pages --store dark_lab
        python manage.py enrich_pages --store dark_lab --limit 50

    """

    help = "Refresh product-page HTML structured data (conditional, on demand)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Register optional store and limit filters."""
        parser.add_argument(
            "--store",
            dest="store",
            default=None,
            help="Limit enrichment to a single store slug (e.g. dark_lab).",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=None,
            help="Process at most this many pages.",
        )

    def handle(self, *_args: object, **options: object) -> None:
        """Run enrichment and print the resulting stats."""
        limit = cast("int | None", options["limit"])
        if limit is not None and limit < 1:
            msg = "--limit must be a positive integer."
            raise CommandError(msg)

        stats = ScraperService.enrich_pages(
            store_slug=cast("str | None", options["store"]),
            limit=limit,
        )
        scope = options["store"] or "all stores"
        self.stdout.write(
            self.style.SUCCESS(
                f"Enrichment ({scope}): checked {stats['checked']}, "
                f"updated {stats['updated']}, failed {stats['failed']}.",
            ),
        )
