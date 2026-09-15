"""Run the real store crawls as an explicit manual verification command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand, CommandError
from scrapy.spiderloader import SpiderLoader
from scrapy.utils.project import get_project_settings

from scrapers.models import ScrapedItem
from scrapers.tasks import run_spider_monitor

if TYPE_CHECKING:
    from argparse import ArgumentParser


def registered_store_spiders() -> dict[str, str]:
    """Return registered spider names and their store slugs."""
    settings = get_project_settings()
    settings.setmodule("scrapers.crawler.settings")
    loader = SpiderLoader.from_settings(settings)
    return {
        name: str(getattr(loader.load(name), "STORE_SLUG", ""))
        for name in loader.list()
    }


class Command(BaseCommand):
    """Verify selected store spiders through the real monitor workflow."""

    help = (
        "Run real scraper monitors for selected stores. This intentionally accesses "
        "the network and executes the same workflow as Celery: it persists "
        "ScrapedItems and Offers and creates a ScraperRun. A successful run also "
        "counts one miss for every active offer of the store it did not see; an "
        "offer is delisted after two successful runs in a row without it. It is "
        "never part of the test suite."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Allow an operator to verify every store or selected stores."""
        spider_names = tuple(registered_store_spiders())
        parser.add_argument(
            "spiders",
            nargs="*",
            choices=spider_names,
            metavar="SPIDER",
        )

    def handle(self, *_args: object, **options: object) -> None:
        """Run each requested crawl and fail after reporting every failure."""
        checks = registered_store_spiders()
        selected = options.get("spiders") or tuple(checks)
        failures = 0
        for spider_name in selected:
            spider = str(spider_name)
            store_slug = checks[spider]
            label = f"Manual verification {spider_name}"
            try:
                result = run_spider_monitor(spider, label)
            except (OSError, RuntimeError, ValueError) as error:
                failures += 1
                self.stderr.write(
                    self.style.ERROR(f"{spider_name}: {error}"),
                )
                continue

            if not ScrapedItem.objects.filter(
                offer__store_slug=store_slug,
            ).exists():
                failures += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"{spider_name}: crawl completed without items for "
                        f"{store_slug}",
                    ),
                )
                continue
            self.stdout.write(self.style.SUCCESS(f"{spider_name}: {result}"))

        if failures:
            message = f"{failures} scraper verification(s) failed."
            raise CommandError(message)
