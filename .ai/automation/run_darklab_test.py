import os
import sys
import django

# Setup Django Environment
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

from scrapers.spiders.dark_lab import DarkLabSpider
from scrapers.models import ScrapedItem

def test_darklab_spider():
    print("Initializing DarkLabSpider...")
    spider = DarkLabSpider()
    
    print("Starting Crawl (Limited by logic)...")
    # Limit categories for speed
    spider.FALLBACK_CATEGORIES = ["whey-protein"] 
    # Force _fetch_categories to return just this one for testing speed
    spider._fetch_categories = lambda: ["whey-protein"]
    
    items = spider.crawl()
    
    print(f"Crawl finished. Returned {len(items)} items (Saved via Service).")
    
    saved_count = ScrapedItem.objects.filter(store_slug="dark_lab").count()
    print(f"Total items in DB for 'dark_lab': {saved_count}")
    
    if saved_count > 0:
        first = ScrapedItem.objects.filter(store_slug="dark_lab").first()
        print(f"Sample Item: {first.name} | Price: {first.price} | Stock: {first.stock_quantity}")
        print(f"Status: {first.get_status_display()} | Stock Status: {first.get_stock_status_display()}")
        
        # Verify specific Shopify logic
        if first.stock_quantity == 100:
             print("Stock Quantity inferred as 100 (likely due to hidden inventory + available=True)")
             
        print("TEST PASSED")
    else:
        print("TEST FAILED: No items saved.")

if __name__ == "__main__":
    test_darklab_spider()
