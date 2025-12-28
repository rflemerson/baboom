from celery import shared_task
from celery.utils.log import get_task_logger

from .services import ScraperService
from .spiders.blackskull import BlackSkullSpider
from .spiders.dark_lab import DarkLabSpider
from .spiders.dux import DuxSpider
from .spiders.growth import GrowthSpider
from .spiders.integral_medica import IntegralMedicaSpider
from .spiders.max_titanium import MaxTitaniumSpider
from .spiders.probiotica import ProbioticaSpider

logger = get_task_logger(__name__)


@shared_task
def scrape_growth_monitor():
    """
    Task to scrape Growth Supplements via API (Wap.Store)
    """
    logger.info("Starting Growth Monitor Task (API)")
    spider = GrowthSpider()
    items = spider.crawl()

    saved_count = 0
    for item in items:
        ScraperService.save_product_from_datalayer(
            item, store_url_base="https://www.gsuplementos.com.br", store_slug="growth"
        )
        saved_count += 1

    return f"Growth Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_blackskull_monitor():
    """
    Task to scrape Black Skull via API (VTEX GraphQL)
    """
    logger.info("Starting Black Skull Monitor Task (API)")
    spider = BlackSkullSpider()
    items = spider.crawl()

    saved_count = 0
    for item in items:
        # Pass generic domain, though spider should try to find specific URL
        ScraperService.save_product_from_datalayer(
            item,
            store_url_base="https://www.blackskullusa.com.br",
            store_slug="black_skull",
        )
        saved_count += 1

    return f"Black Skull Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_integral_monitor():
    logger.info("Starting Integral Medica Monitor Task")
    spider = IntegralMedicaSpider()
    items = spider.crawl()

    saved_count = 0
    for item in items:
        ScraperService.save_product_from_datalayer(
            item,
            store_url_base="https://www.integralmedica.com.br",
            store_slug="integral_medica",
        )
        saved_count += 1

    return f"Integral Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_maxtitanium_monitor():
    logger.info("Starting Max Titanium Monitor Task")
    spider = MaxTitaniumSpider()
    items = spider.crawl()

    saved_count = 0
    for item in items:
        # Pass generic domain
        ScraperService.save_product_from_datalayer(
            item,
            store_url_base="https://www.maxtitanium.com.br",
            store_slug="max_titanium",
        )
        saved_count += 1

    return f"Max Titanium Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_probiotica_monitor():
    logger.info("Starting Probiótica Monitor Task")
    spider = ProbioticaSpider()
    items = spider.crawl()

    saved_count = 0
    for item in items:
        ScraperService.save_product_from_datalayer(
            item,
            store_url_base="https://www.probiotica.com.br",
            store_slug="probiotica",
        )
        saved_count += 1

    return f"Probiótica Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_darklab_monitor():
    logger.info("Starting Dark Lab Monitor Task")
    spider = DarkLabSpider()
    items = spider.crawl()

    saved_count = 0
    for item in items:
        ScraperService.save_product_from_datalayer(
            item,
            store_url_base="https://www.darklabsuplementos.com.br",
            store_slug="dark_lab",
        )
        saved_count += 1

    return f"Dark Lab Monitor: Saved/Updated {saved_count} items."


@shared_task
def scrape_dux_monitor():
    logger.info("Starting Dux Nutrition Monitor Task")
    spider = DuxSpider()
    items = spider.crawl()

    saved_count = 0
    for item in items:
        ScraperService.save_product_from_datalayer(
            item, store_url_base="https://www.duxhumanhealth.com", store_slug="dux"
        )
        saved_count += 1

    return f"Dux Monitor: Saved/Updated {saved_count} items."
