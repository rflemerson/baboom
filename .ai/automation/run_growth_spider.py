import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

from scrapers.spiders.growth import GrowthSpider
from scrapers.models import ScrapedItem

def test_spider():
    print("Initializing GrowthSpider...")
    spider = GrowthSpider()
    
    print("Starting Crawl (Limited usually by spider logic, but we will see)...")
    # You might want to temporarily limit categories in the spider if it takes too long
    # But for now let's let it run or modify the instance
    spider.FALLBACK_CATEGORIES = ["/vegano/"] # Test with a smaller category first? Or just let it run
    
    items = spider.crawl()
    
    print(f"Crawl finished. Returned {len(items)} items.")
    
    saved_count = ScrapedItem.objects.filter(store_slug="growth").count()
    print(f"Total items in DB for 'growth': {saved_count}")
    
    if saved_count > 0:
        first = ScrapedItem.objects.filter(store_slug="growth").first()
        print(f"Sample Item: {first.name} | Price: {first.price} | Stock: {first.stock_quantity}")
        print("TEST PASSED")
    else:
        print("TEST FAILED: No items saved.")

if __name__ == "__main__":
    test_spider()
