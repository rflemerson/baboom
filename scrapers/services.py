import logging
from decimal import Decimal
from typing import Any

from django.db import transaction

from core.models import (
    ProductPriceHistory,
    ProductStore,
    Store,
)

logger = logging.getLogger(__name__)


class ScraperService:
    @staticmethod
    @transaction.atomic
    def save_product_from_datalayer(data: dict[str, Any], store_url_base: str):
        """
        Saves or updates a product based on dataLayer info using Hybrid Strategy.
        - Existing Product: Update Price History + Create ScrapedItem (Linked)
        - New Product: Create ScrapedItem (New) ONLY.
        """
        from .models import ScrapedItem

        external_id = str(data.get("item_id"))
        price = Decimal(str(data.get("price", "0.00")))
        product_url = data.get("url", store_url_base)

        # Decide Store Name based on URL or input
        store_slug = (
            "growth"  # Default for now based on legacy logic, or derive from URL
        )
        if "blackskull" in store_url_base:
            store_slug = "blackskull"
        elif "darklab" in store_url_base:
            store_slug = "darklab"
        elif "integral" in store_url_base:
            store_slug = "integral"

        # Ensure URL is legitimate for unique constraint
        # Some spiders send relative or broken URLs, we try to rely on what passed
        if not product_url or len(product_url) > 490:
            # Fallback or truncate to avoid db error
            product_url = product_url[:490] if product_url else ""

        # 1. Store Resolution
        store, _ = Store.objects.get_or_create(
            name=store_slug,
            defaults={
                "display_name": store_slug.title(),
                "description": "Auto-generated store",
            },
        )

        # 2. Check for Existing Link
        existing_link = ProductStore.objects.filter(
            store=store, external_id=external_id
        ).first()

        product_store = None
        status = ScrapedItem.Status.NEW

        if existing_link:
            # BRANCH A: Existing Product
            product_store = existing_link
            status = ScrapedItem.Status.LINKED

            # Update Price History
            ProductPriceHistory.objects.create(
                store_product_link=product_store,
                price=price,
                stock_status=ProductPriceHistory.StockStatus.AVAILABLE,  # Simplified
            )
            logger.info(
                f"Updated price for existing product: {product_store.product.name}"
            )

        else:
            # BRANCH B: New (Raw) Item
            # We explicitly DO NOT create a Product here.
            logger.info(
                f"New item discovered (Staging): {data.get('item_name')} [{external_id}]"
            )
            pass

        # 3. Save ScrapedItem (Raw Data Lake)
        # Use update_or_create on URL to avoid duplicates in staging,
        # or use external_id + store if URL varies.
        # Prefer external_id + store for uniqueness if possible, but URL is often safer for scrapers.
        # Let's use external_id + store as the logical key for the Item, but URL is the unique field in model.
        # If URL changes for same ID, we might have conflict. Let's just try-catch or query first.

        # We'll rely on external_id + store to find existing ScrapedItem to update it
        defaults = {
            "url": product_url,
            "raw_data": data,
            "status": status,
            "product_store": product_store,
        }

        # Try to find by store+external_id first (more stable than URL)
        # ScrapedItem doesn't have unique constraint on (store, external_id) yet, but should.
        # But `url` is unique.
        # Let's update if we find one by URL.

        obj, created = ScrapedItem.objects.update_or_create(
            url=product_url,
            defaults={
                "store": store_slug,
                "external_id": external_id,
                "raw_data": data,
                "status": status,
                "product_store": product_store,
            },
        )
        return obj

    @staticmethod
    @transaction.atomic
    def promote_scraped_item(scraped_item):
        """
        Promotes a ScrapedItem to a real Product in the Core app.
        """
        from django.utils.text import slugify

        from core.models import (
            Brand,
            Category,
            Product,
            ProductPriceHistory,
            ProductStore,
            Store,
        )

        data = scraped_item.raw_data

        external_id = str(data.get("item_id"))
        name = data.get("item_name")
        price = Decimal(str(data.get("price", "0.00")))
        brand_name = data.get("item_brand", "Generic Brand")
        category_name = data.get("item_list_name", "")  # Often raw from spider
        weight = int(data.get("weight", 0))

        if not name:
            logger.warning(f"Cannot promote item {scraped_item.id}: Missing name")
            return None

        # 1. Resolve Store (from ScrapedItem)
        store_slug = scraped_item.store
        store, _ = Store.objects.get_or_create(
            name=store_slug,
            defaults={
                "display_name": store_slug.title(),
                "description": "Auto-generated store",
            },
        )

        # 2. Resolve Brand
        brand_slug = slugify(brand_name)
        brand = Brand.objects.filter(display_name__iexact=brand_name).first()
        if not brand:
            brand = Brand.objects.filter(name__iexact=brand_slug).first()
        if not brand:
            brand = Brand.objects.create(name=brand_slug, display_name=brand_name)

        # 3. Resolve Category (Simple)
        category = None
        if category_name:
            category = Category.objects.filter(name__iexact=category_name).first()
            if not category:
                # Create root category if not exists
                category = Category.add_root(
                    name=category_name,
                    description=f"Auto-promoted category: {category_name}",
                )

        # 4. Create/Get Product
        # We try to find existing product by Name+Brand to avoid creating dupes
        # (even if not linked yet)
        product = Product.objects.filter(brand=brand, name=name).first()

        if not product:
            product = Product.objects.create(
                name=name,
                brand=brand,
                category=category,
                weight=weight,
                is_manually_curated=False,
            )
            logger.info(f"Promoted: Created new product {product}")
        else:
            logger.info(f"Promoted: Matched existing product {product}")

        # 5. Create ProductStore Link
        product_store, _ = ProductStore.objects.update_or_create(
            store=store,
            product=product,
            defaults={
                "external_id": external_id,
                "product_link": scraped_item.url,
            },
        )

        # 6. Create Price History (Initial)
        ProductPriceHistory.objects.create(
            store_product_link=product_store,
            price=price,
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
        )

        # 7. Update ScrapedItem
        scraped_item.status = scraped_item.Status.LINKED
        scraped_item.product_store = product_store
        scraped_item.save()

        return product
