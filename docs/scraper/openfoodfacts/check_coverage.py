
import os
import django
import logging
import time
import argparse
from typing import List, Tuple

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baboom.settings')
django.setup()

from scrapers.models import ScrapedItem
from openfoodfacts import API

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

def check_db_coverage(limit: int = 0):
    """
    Queries DB for unique EANs and checks Open Food Facts coverage.
    Does NOT run any scrapers.
    """
    print("\n=== CHECKING OPEN FOOD FACTS COVERAGE (FROM DB) ===\n")
    
    # Get all distinct non-empty EANs
    qs = ScrapedItem.objects.filter(ean__isnull=False).exclude(ean='').values_list('ean', flat=True).distinct()
    
    if limit > 0:
        qs = qs[:limit]
        
    eans = list(qs)
    total_eans = len(eans)
    
    if total_eans == 0:
        print("No EANs found in database. Run scrapers first to populate ScrapedItem table.")
        return

    print(f"Found {total_eans} unique EANs in database. Querying OFF API...")
    
    api = API(user_agent="BaboomCoverageCheck/1.0", country="br")
    
    found_count = 0
    missing_count = 0
    errors = 0
    
    for i, ean in enumerate(eans, 1):
        try:
            # Rate limit politeness
            time.sleep(0.5)
            
            product = api.product.get(ean)
            
            if product:
                found_count += 1
                name = product.get('product_name') or "Unknown Name"
                nutriments = product.get('nutriments', {})
                protein = nutriments.get('proteins_100g')
                
                # Format protein to string if None
                prot_str = f"{protein}g" if protein is not None else "N/A"
                
                print(f"[{i}/{total_eans}] ✅ FOUND {ean}: {name[:40]:<40} | Prot: {prot_str}")
            else:
                missing_count += 1
                print(f"[{i}/{total_eans}] ❌ MISSING {ean}")
                
        except Exception as e:
            errors += 1
            print(f"[{i}/{total_eans}] ⚠️ ERROR {ean}: {e}")

    print("\n" + "="*30)
    print("       FINAL REPORT       ")
    print("="*30)
    print(f"Total Unique EANs: {total_eans}")
    print(f"Found on OFF:      {found_count}")
    print(f"Missing on OFF:    {missing_count}")
    print(f"Errors:            {errors}")
    if total_eans > 0:
        coverage = (found_count / total_eans) * 100
        print(f"Coverage Rate:     {coverage:.2f}%")
    print("="*30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check Open Food Facts coverage against database EANs.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of EANs to check (0 for all)")
    args = parser.parse_args()
    
    check_db_coverage(limit=args.limit)
