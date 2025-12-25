import os
import random
import sys
from decimal import Decimal

import django

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

from core.models import (
    Brand,
    Category,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
)


def run_seed():
    print("🌱 Seeding database from .ai/seed.py...")

    # Clear existing data
    Product.objects.all().delete()
    Brand.objects.all().delete()
    Store.objects.all().delete()
    Category.objects.all().delete()

    # 1. Categories
    cat_protein = Category.add_root(name="Proteins")
    cat_creatine = Category.add_root(name="Creatine")

    # 2. Brands
    brands = [
        Brand.objects.create(name=f"Brand {i}", display_name=f"Power Brand {i}")
        for i in range(1, 4)
    ]

    # 3. Stores
    stores = [
        Store.objects.create(name="Amazon", display_name="Amazon"),
        Store.objects.create(name="MercadoLivre", display_name="Mercado Livre"),
    ]

    # 4. Products
    products_data = [
        ("Whey Protein Isolate", 900, cat_protein),
        ("Whey Native", 800, cat_protein),
        ("Creatine Mono", 300, cat_creatine),
        ("Vegan Protein", 500, cat_protein),
        ("Mass Gainer", 3000, cat_protein),
    ]

    for i, (name, weight, cat) in enumerate(products_data):
        p = Product.objects.create(
            name=f"{name} {i + 1}",
            brand=random.choice(brands),
            weight=weight,
            category=cat,
        )

        # Nutrition
        prot = Decimal(random.randint(20, 28))
        serving = 30

        fact = NutritionFacts.objects.create(
            serving_size_grams=serving,
            proteins=prot,
            carbohydrates=Decimal("2.0"),
            total_fats=Decimal("1.5"),
            description=f"Nutri for {p.name}",
            energy_kcal=120,
        )
        ProductNutrition.objects.create(product=p, nutrition_facts=fact)

        # Price
        link = ProductStore.objects.create(
            product=p,
            store=random.choice(stores),
            product_link="http://example.com/product",
            external_id=f"SKU-{i}",
        )
        ProductPriceHistory.objects.create(
            store_product_link=link, price=Decimal(random.randint(80, 200))
        )

    print("✅ Successfully seeded database with 5 products!")


if __name__ == "__main__":
    run_seed()
