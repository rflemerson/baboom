import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

from scrapers.spiders.dux import DuxSpider
from scrapers.models import ScrapedItem

def test_dux_spider():
    print("Initializing DuxSpider...")
    spider = DuxSpider()
    
    print("Starting Crawl (Limited by logic)...")
    # Limit categories for speed
    spider.FALLBACK_CATEGORIES = ["proteinas"] 
    # Force _fetch_categories to return empty or minimal if we want to skip dynamic fetching
    # But let's verify dynamic fetching too if possible, it usually works for Dux.
    
    items = spider.crawl()
    
    print(f"Crawl finished. Returned {len(items)} items (Saved via Service).")
    
    saved_count = ScrapedItem.objects.filter(store_slug="dux_nutrition").count()
    print(f"Total items in DB for 'dux_nutrition': {saved_count}")
    
    if saved_count > 0:
        first = ScrapedItem.objects.filter(store_slug="dux_nutrition").first()
        print(f"Sample Item: {first.name} | Price: {first.price} | Stock: {first.stock_quantity}")
        print(f"Status: {first.get_status_display()} | Stock Status: {first.get_stock_status_display()}")
        print("TEST PASSED")
    else:
        print("TEST FAILED: No items saved.")

if __name__ == "__main__":
    test_dux_spider()
