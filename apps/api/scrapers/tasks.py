"""Celery tasks for running scraper monitors and recovery jobs."""

from datetime import timedelta
from typing import TYPE_CHECKING

from celery import shared_task
from celery._state import get_current_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .models import ScrapedItem, ScraperRun
from .services import ScraperService
from .spiders.blackskull import BlackSkullSpider
from .spiders.dark_lab import DarkLabSpider
from .spiders.dux import DuxSpider
from .spiders.growth import GrowthSpider
from .spiders.integral_medica import IntegralMedicaSpider
from .spiders.max_titanium import MaxTitaniumSpider
from .spiders.probiotica import ProbioticaSpider
from .spiders.soldiers import SoldiersSpider

if TYPE_CHECKING:
    from .spiders.base_spider import BaseSpider

logger = get_task_logger(__name__)

STUCK_ITEM_TIMEOUT_MINUTES = 60


class EmptyMonitorRunError(RuntimeError):
    """A monitor that used to return products returned none."""


def _monitor_has_produced_items(label: str) -> bool:
    """Whether this monitor ever completed a run carrying products.

    The expectation comes from the store's own history rather than a tuned
    threshold: a monitor that has produced items and now returns none is
    pointing at something that changed, while a brand new store legitimately
    starts empty.
    """
    return ScraperRun.objects.filter(
        label=label,
        status=ScraperRun.Status.SUCCESS,
        items_count__gt=0,
    ).exists()


def _finish_run(
    run: ScraperRun,
    *,
    status: str,
    message: str,
    items_count: int = 0,
    error_message: str = "",
) -> None:
    """Close a scraper run record with its outcome."""
    finished_at = timezone.now()
    run.status = status
    run.finished_at = finished_at
    run.duration_ms = int((finished_at - run.started_at).total_seconds() * 1000)
    run.items_count = items_count
    run.message = message
    run.error_message = error_message
    run.save(
        update_fields=(
            "status",
            "finished_at",
            "duration_ms",
            "items_count",
            "message",
            "error_message",
        ),
    )


def _run_spider_monitor(spider_class: type[BaseSpider], label: str) -> str:
    """Run a light catalog spider (price/stock/basic) and return a status message.

    Product-page HTML enrichment is a separate, on-demand job
    (:func:`enrich_store_pages`); the monitors never touch it.
    """
    current_task = get_current_task()
    run = ScraperRun.objects.create(
        label=label,
        task_name=current_task.name if current_task else "",
    )
    logger.info("Starting %s monitor task", label)
    try:
        items = spider_class().crawl()
    except Exception as exc:
        _finish_run(
            run,
            status=ScraperRun.Status.ERROR,
            message=f"{label} Monitor failed.",
            error_message=str(exc),
        )
        logger.exception("%s monitor task failed", label)
        raise

    if not items and _monitor_has_produced_items(label):
        message = (
            f"{label} Monitor returned no products, but previous runs did. "
            f"The store layout or endpoint has most likely changed."
        )
        _finish_run(
            run,
            status=ScraperRun.Status.ERROR,
            message=f"{label} Monitor returned no products.",
            error_message=message,
        )
        logger.error(message)
        raise EmptyMonitorRunError(message)

    message = f"{label} Monitor: Saved/Updated {len(items)} items."
    _finish_run(
        run,
        status=ScraperRun.Status.SUCCESS,
        message=message,
        items_count=len(items),
    )
    logger.info(message)
    return message


@shared_task
def scrape_growth_monitor() -> str:
    """Scrape Growth Supplements via API."""
    return _run_spider_monitor(GrowthSpider, "Growth")


@shared_task
def scrape_blackskull_monitor() -> str:
    """Scrape Black Skull via API."""
    return _run_spider_monitor(BlackSkullSpider, "Black Skull")


@shared_task
def scrape_integral_monitor() -> str:
    """Scrape Integral Medica."""
    return _run_spider_monitor(IntegralMedicaSpider, "Integral Medica")


@shared_task
def scrape_maxtitanium_monitor() -> str:
    """Scrape Max Titanium."""
    return _run_spider_monitor(MaxTitaniumSpider, "Max Titanium")


@shared_task
def scrape_probiotica_monitor() -> str:
    """Scrape Probiotica."""
    return _run_spider_monitor(ProbioticaSpider, "Probiotica")


@shared_task
def scrape_darklab_monitor() -> str:
    """Scrape Dark Lab."""
    return _run_spider_monitor(DarkLabSpider, "Dark Lab")


@shared_task
def scrape_dux_monitor() -> str:
    """Scrape Dux Nutrition."""
    return _run_spider_monitor(DuxSpider, "Dux")


@shared_task
def scrape_soldiers_monitor() -> str:
    """Scrape Soldiers Nutrition."""
    return _run_spider_monitor(SoldiersSpider, "Soldiers")


@shared_task
def enrich_store_pages(
    store_slug: str | None = None,
    limit: int | None = None,
) -> str:
    """On-demand heavy pass: refresh product-page HTML for scraped pages.

    Run this when you want fresh structured data (e.g.
    ``enrich_store_pages.delay("dark_lab")``). Each page is re-fetched with a
    conditional GET, so only pages the store reports as changed are updated.
    """
    stats = ScraperService.enrich_pages(store_slug=store_slug, limit=limit)
    scope = store_slug or "all stores"
    return (
        f"Enrichment ({scope}): checked {stats['checked']}, "
        f"updated {stats['updated']}, unchanged {stats['unchanged']}, "
        f"failed {stats['failed']}."
    )


@shared_task
def release_stuck_items() -> str:
    """Return expired interactive reservations to the review queue."""
    timeout = timezone.now() - timedelta(minutes=STUCK_ITEM_TIMEOUT_MINUTES)

    stuck_items = ScrapedItem.objects.filter(
        status=ScrapedItem.Status.PROCESSING,
        last_attempt_at__lt=timeout,
    )

    count = stuck_items.update(
        status=ScrapedItem.Status.QUEUED,
        last_attempt_at=None,
        updated_at=timezone.now(),
    )
    if count > 0:
        return f"Cleaned up {count} stuck items."

    return "No stuck items found."
