
import os
import django
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

from scrapers.models import ScrapedItem
from agents.brain.raw_extraction_agent import run_raw_extraction

def check(item_id):
    from agents.client import AgentClient
    from agents.storage import get_storage
    from agents.tools.scraper import ScraperService
    import json
    
    client = AgentClient()
    storage = get_storage()
    service = ScraperService()
    
    item_data = client.checkout_work(target_item_id=item_id, force=True)
    storage_path = service.download_assets(item_id, item_data['productLink'])
    
    # Extract metadata using the new logic
    meta = service.extract_metadata(storage_path, item_data['productLink'])
    raw_dat = service.consolidate(meta)
    
    bucket, _ = storage_path.split("/", 1)
    cand_key = "candidates.json"
    candidates_json = storage.download(bucket, cand_key)
    candidates = json.loads(candidates_json)
    
    valid_imgs = [c for c in candidates if c["score"] > 0]
    valid_imgs.sort(key=lambda x: x["score"], reverse=True)
    top_images = [f"{bucket}/{c['file']}" for c in valid_imgs[:8]]
    
    print(f"Processing Item {item_id}")
    print(f"Top Images: {top_images}")
    # print(f"Description Preview: {raw_dat.description[:200]}...")
    
    raw_text = run_raw_extraction(
        item_data.get('productLink'),
        raw_dat.description, # Pass the enriched description
        top_images
    )
    
    print("\n=== RAW EXTRACTION OUTPUT ===")
    print(raw_text)
    print("==============================\n")

if __name__ == "__main__":
    import sys
    item_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    check(item_id)
