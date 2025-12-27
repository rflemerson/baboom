from celery import shared_task

from .spiders.growth import GrowthSpider


@shared_task
def scrape_growth_monitor():
    """
    A simple monitoring task that fetches the Growth Supplements homepage
    to verify connectivity and basic spider functionality.
    """
    spider = GrowthSpider()
    success = spider.fetch_home()

    if success:
        return "Growth Monitor: Success"
    return "Growth Monitor: Failed"
