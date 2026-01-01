from django.db.models.signals import post_save
from django.dispatch import receiver

from scrapers.models import ScrapedItem
from scrapers.services import ScraperService


@receiver(post_save, sender=ScrapedItem)
def sync_scraped_item_to_core(sender, instance, **kwargs):
    """
    Quando um ScrapedItem é salvo, tenta sincronizar preço/estoque
    se estiver LINKED.
    """
    if instance.status == ScrapedItem.Status.LINKED:
        ScraperService.sync_price_to_core(instance)
