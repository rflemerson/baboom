import logging
import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

logging.basicConfig(level=logging.DEBUG)

from scrapers.spiders.blackskull import BlackSkullSpider
from scrapers.models import ScrapedItem

def test_blackskull_spider():
    print("Initializing BlackSkullSpider...")
    spider = BlackSkullSpider()
    
    print("Starting Crawl (Limited by logic)...")
    spider.FALLBACK_CATEGORIES = ["proteina"] 
    spider._fetch_categories = lambda: ["proteina"]
    
    items = spider.crawl()
    
    print(f"Crawl finished. Returned {len(items)} items (Saved via Service).")
    
    saved_count = ScrapedItem.objects.filter(store_slug="black_skull").count()
    print(f"Total items in DB for 'black_skull': {saved_count}")
    
    if saved_count > 0:
        first = ScrapedItem.objects.filter(store_slug="black_skull").first()
        print(f"Sample Item: {first.name} | Price: {first.price} | Stock: {first.stock_quantity}")
        print(f"Status: {first.get_status_display()} | Stock Status: {first.get_stock_status_display()}")
        print("TEST PASSED")
    else:
        print("TEST FAILED: No items saved.")

if __name__ == "__main__":
    test_blackskull_spider()
