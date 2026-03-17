from datetime import timedelta

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

logger = get_task_logger(__name__)


@shared_task
def scrape_growth_monitor():
    """Scrape Growth Supplements via API."""
    logger.info("Starting Growth Monitor Task (API)")
    spider = GrowthSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Growth Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_blackskull_monitor():
    """Scrape Black Skull via API."""
    logger.info("Starting Black Skull Monitor Task (API)")
    spider = BlackSkullSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Black Skull Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_integral_monitor():
    """Scrape Integral Medica."""
    logger.info("Starting Integral Medica Monitor Task")
    spider = IntegralMedicaSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Integral Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_maxtitanium_monitor():
    """Scrape Max Titanium."""
    logger.info("Starting Max Titanium Monitor Task")
    spider = MaxTitaniumSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Max Titanium Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_probiotica_monitor():
    """Scrape Probiotica."""
    logger.info("Starting Probiotica Monitor Task")
    spider = ProbioticaSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Probiotica Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_darklab_monitor():
    """Scrape Dark Lab."""
    logger.info("Starting Dark Lab Monitor Task")
    spider = DarkLabSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Dark Lab Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_dux_monitor():
    """Scrape Dux Nutrition."""
    logger.info("Starting Dux Monitor Task")
    spider = DuxSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Dux Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_soldiers_monitor():
    """Scrape Soldiers Nutrition."""
    logger.info("Starting Soldiers Nutrition Monitor Task")
    spider = SoldiersSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Soldiers Monitor: Saved/Updated {saved_count} items."


@shared_task
def release_stuck_items():
    """Unlock items stuck in PROCESSING state.

    Cleaner: Unlocks items that have been in PROCESSING for too long
    (e.g., agent died or timed out without reporting).
    """
    timeout = timezone.now() - timedelta(minutes=60)

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
