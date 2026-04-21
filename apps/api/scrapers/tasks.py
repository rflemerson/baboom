"""Celery tasks for running scraper monitors and recovery jobs."""

from datetime import timedelta
from typing import TYPE_CHECKING

from celery import shared_task
from celery._state import get_current_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .models import ScrapedItem, ScraperRun
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


def _run_spider_monitor(spider_class: type[BaseSpider], label: str) -> str:
    """Run a scraper spider and return a standardized status message."""
    started_at = timezone.now()
    current_task = get_current_task()
    run = ScraperRun.objects.create(
        label=label,
        task_name=current_task.name if current_task else "",
    )
    logger.info("Starting %s monitor task", label)
    try:
        items = spider_class().crawl()
    except Exception as exc:
        finished_at = timezone.now()
        run.status = ScraperRun.Status.ERROR
        run.finished_at = finished_at
        run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        run.error_message = str(exc)
        run.message = f"{label} Monitor failed."
        run.save(
            update_fields=(
                "status",
                "finished_at",
                "duration_ms",
                "error_message",
                "message",
            ),
        )
        logger.exception("%s monitor task failed", label)
        raise

    finished_at = timezone.now()
    message = f"{label} Monitor: Saved/Updated {len(items)} items."
    run.status = ScraperRun.Status.SUCCESS
    run.finished_at = finished_at
    run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    run.items_count = len(items)
    run.message = message
    run.save(
        update_fields=(
            "status",
            "finished_at",
            "duration_ms",
            "items_count",
            "message",
        ),
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
def release_stuck_items() -> str:
    """Move stale processing items back into the retry flow."""
    timeout = timezone.now() - timedelta(minutes=STUCK_ITEM_TIMEOUT_MINUTES)

    stuck_items = ScrapedItem.objects.filter(
        status=ScrapedItem.Status.PROCESSING,
        last_attempt_at__lt=timeout,
    )

    count = stuck_items.count()
    if count > 0:
        stuck_items.update(
            status=ScrapedItem.Status.ERROR,
            last_error_log="System: Timeout - Agent stopped responding (Zombie Task).",
        )
        return f"Cleaned up {count} stuck items."

    return "No stuck items found."
