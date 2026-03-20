"""Celery tasks for running scraper monitors and recovery jobs."""

from datetime import timedelta
from typing import TYPE_CHECKING

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .models import ScrapedItem
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
    logger.info("Starting %s monitor task", label)
    items = spider_class().crawl()
    return f"{label} Monitor: Saved/Updated {len(items)} items."


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
