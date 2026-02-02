
import os
import sys
import django
import json

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

from scrapers.spiders.soldiers import SoldiersSpider

def run():
    print("Initializing Spider...")
    spider = SoldiersSpider()
    # Limit categories for test speed if possible?
    # spider.categories_to_crawl = ["creatina"] # fallback override?
    # SoldiersSpider uses discovery. We can mock _discover_categories?
    
    # Let's monkeypatch for speed
    def mock_discover():
        print("MOCK: Discovering only 'proteinas' for test speed.")
        return ["proteinas"]
    
    spider._discover_categories = mock_discover
    
    items = spider.crawl()
    ids = [item.id for item in items]
    print(json.dumps(ids))

if __name__ == "__main__":
    run()
