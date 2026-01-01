from django.db.models.signals import post_save
from django.dispatch import receiver

from scrapers.models import ScrapedItem
from scrapers.services import ScraperService


@receiver(post_save, sender=ScrapedItem)
def sync_scraped_item_to_core(sender, instance, **kwargs):
    """
    When a ScrapedItem is saved, attempt to sync price/stock
    if its status is LINKED.
    """
    if instance.status == ScrapedItem.Status.LINKED:
        ScraperService.sync_price_to_core(instance)
