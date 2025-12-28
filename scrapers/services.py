import logging
import re
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils.text import slugify

from core.models import (
    Brand,
    Category,
    Product,
    ProductPriceHistory,
    ProductStore,
    Store,
)

logger = logging.getLogger(__name__)


class ScraperService:
    @staticmethod
    def _extract_weight(name: str) -> int:
        """
        Attempts to extract weight in grams from product name.
        E.g. "Whey 1kg" -> 1000, "Creatina 300g" -> 300.
        Defaults to 0 if not found.
        """
        # Patterns for kg and g
        kg_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kg|Kg|KG)", name)
        if kg_match:
            val = float(kg_match.group(1).replace(",", "."))
            return int(val * 1000)

        g_match = re.search(
            r"(\d+)\s*(?:g|G)(?!\w)", name
        )  # negative lookahead to avoid 'green' etc
        if g_match:
            return int(g_match.group(1))

        return 0

    @staticmethod
    @transaction.atomic
    def save_product_from_datalayer(data: dict[str, Any], store_url_base: str):
        """
        Saves or updates a product based on dataLayer info.
        data schema expected:
        {
            "item_id": 123,
            "item_name": "Product Name",
            "price": 100.00,
            "item_brand": "Growth",
            "item_list_name": "Category",
            "url": "https://..." (Optional)
        }
        """
        external_id = str(data.get("item_id"))
        name = data.get("item_name")
        price = Decimal(str(data.get("price", "0.00")))
        brand_name = data.get("item_brand", "Growth Supplements")
        category_name = data.get("item_list_name", "")
        product_url = data.get("url", store_url_base)

        if not external_id or not name:
            logger.warning(f"Skipping item due to missing ID or Name: {data}")
            return None

        # 1. Brands & Category
        # Robust Brand Lookup
        brand_slug = slugify(brand_name)
        brand = Brand.objects.filter(display_name__iexact=brand_name).first()
        if not brand:
            brand = Brand.objects.filter(name__iexact=brand_slug).first()

        if not brand:
            brand = Brand.objects.create(name=brand_slug, display_name=brand_name)

        category = None
        if category_name:
            # Simple Category matching/creation
            category = Category.objects.filter(name=category_name).first()
            if not category:
                # Treebeard requires add_root for new root nodes
                category = Category.add_root(
                    name=category_name,
                    description=f"Imported category: {category_name}",
                )

        # 2. Store (Growth)
        store, _ = Store.objects.get_or_create(
            name="growth",
            defaults={
                "display_name": "Growth Supplements",
                "description": "Loja Oficial",
            },
        )

        # 3. Product Resolution
        # Try to find by External ID first (Most reliable connection)
        product = None
        created = False

        # Check if we already have a link for this store item
        existing_link = ProductStore.objects.filter(
            store=store, external_id=external_id
        ).first()

        if existing_link:
            product = existing_link.product
        else:
            # Fallback: Try to find by Name + Brand (to avoid duplicates if re-scraping new store IDs for same product)
            weight = ScraperService._extract_weight(name)
            product = Product.objects.filter(
                brand=brand, name=name, weight=weight
            ).first()

            if not product:
                # Create New Product
                product = Product.objects.create(
                    name=name,
                    brand=brand,
                    category=category,
                    weight=weight,
                    is_manually_curated=False,  # Explicitly marking as system-managed
                )
                created = True
                logger.info(f"Created new product: {product}")
            else:
                logger.info(f"Matched existing product by name: {product}")

        # 4. Updates (Curator Lock Check)
        if not created:
            if product.is_manually_curated:
                logger.info(f"Skipping static update for {product} (Manually Curated)")
            else:
                # "Create Only" strategy for static fields means we usually DON'T update name/desc
                # unless we want to "repair" empty fields.
                # For now, we strictly respect the "Don't overwrite" rule for existing items.
                pass

        # 5. ProductStore Link
        product_store, _ = ProductStore.objects.update_or_create(
            store=store,
            product=product,
            defaults={"external_id": external_id, "product_link": product_url},
        )

        # 6. Price History (Always track)
        ProductPriceHistory.objects.create(
            store_product_link=product_store,
            price=price,
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
        )

        return product
