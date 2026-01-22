from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def scrape_growth_monitor():
    """
    Task to scrape Growth Supplements via API (Wap.Store)
    """
    from .spiders.growth import GrowthSpider

    logger.info("Starting Growth Monitor Task (API)")
    spider = GrowthSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Growth Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_blackskull_monitor():
    """
    Task to scrape Black Skull via API (VTEX GraphQL)
    """
    from .spiders.blackskull import BlackSkullSpider

    logger.info("Starting Black Skull Monitor Task (API)")
    spider = BlackSkullSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Black Skull Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_integral_monitor():
    from .spiders.integral_medica import IntegralMedicaSpider

    logger.info("Starting Integral Medica Monitor Task")
    spider = IntegralMedicaSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Integral Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_maxtitanium_monitor():
    from .spiders.max_titanium import MaxTitaniumSpider

    logger.info("Starting Max Titanium Monitor Task")
    spider = MaxTitaniumSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Max Titanium Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_probiotica_monitor():
    from .spiders.probiotica import ProbioticaSpider

    logger.info("Starting Probiotica Monitor Task")
    spider = ProbioticaSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Probiotica Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_darklab_monitor():
    from .spiders.dark_lab import DarkLabSpider

    logger.info("Starting Dark Lab Monitor Task")
    spider = DarkLabSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Dark Lab Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_dux_monitor():
    from .spiders.dux import DuxSpider

    logger.info("Starting Dux Monitor Task")
    spider = DuxSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Dux Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_soldiers_monitor():
    from .spiders.soldiers import SoldiersSpider

    logger.info("Starting Soldiers Nutrition Monitor Task")
    spider = SoldiersSpider()
    items = spider.crawl()
    saved_count = len(items)
    return f"Soldiers Monitor: Saved/Updated {saved_count} items."
