# fmt: off
# ruff: noqa
import os
import random
import sys
from datetime import timedelta
from decimal import Decimal

import django
from django.utils import timezone

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

from core.models import (
    Brand,
    Category,
    Flavor,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
    Tag,
)


def run_seed():
    print("🌱 Seeding database with EXPANDED real data...")

    # Clear existing data
    ProductPriceHistory.objects.all().delete()
    ProductStore.objects.all().delete()
    ProductNutrition.objects.all().delete()
    NutritionFacts.objects.all().delete()
    Product.objects.all().delete()
    Brand.objects.all().delete()
    Store.objects.all().delete()
    Category.objects.all().delete()
    Tag.objects.all().delete()
    Flavor.objects.all().delete()

    # 1. Categories (Tree)
    cat_proteins = Category.add_root(name="Proteínas")
    cat_whey = cat_proteins.add_child(name="Whey Protein")
    cat_whey_conc = cat_whey.add_child(name="Concentrado")
    cat_whey_iso = cat_whey.add_child(name="Isolado")
    cat_whey_hydro = cat_whey.add_child(name="Hidrolisado")
    cat_creatine = Category.add_root(name="Creatina")
    cat_vegan = Category.add_root(name="Vegano")  # Made Root for visibility

    print(f"Created Categories: {Category.objects.count()}")

    # 2. Tags (Tree)
    tag_goals = Tag.add_root(name="Objetivos")
    tag_mass = tag_goals.add_child(name="Ganho de Massa")
    tag_weight_loss = tag_goals.add_child(name="Emagrecimento")
    tag_energy = tag_goals.add_child(name="Energia e Foco")
    tag_recovery = tag_goals.add_child(name="Recuperação")

    tag_diet = Tag.add_root(name="Restrições Alimentares")
    tag_gluten_free = tag_diet.add_child(name="Sem Glúten")
    tag_lactose_free = tag_diet.add_child(name="Zero Lactose")
    tag_sugar_free = tag_diet.add_child(name="Zero Açúcar")
    tag_vegan_tag = tag_diet.add_child(name="Vegano")

    print(f"Created Tags: {Tag.objects.count()}")

    # 3. Flavors
    flavors_list = [
        "Chocolate",
        "Morango",
        "Baunilha",
        "Cookies & Cream",
        "Natural",
        "Limão",
        "Doce de Leite",
        "Brigadeiro",
        "Açaí com Guaraná",
        "Sem Sabor",
    ]
    flavor_objs = {}
    for f_name in flavors_list:
        flavor_objs[f_name] = Flavor.objects.create(name=f_name)

    print(f"Created Flavors: {Flavor.objects.count()}")

    # 4. Brands
    brand_growth = Brand.objects.create(
        name="growth", display_name="Growth Supplements"
    )
    brand_max = Brand.objects.create(name="maxtitanium", display_name="Max Titanium")
    brand_dux = Brand.objects.create(name="dux", display_name="Dux Nutrition")
    brand_integral = Brand.objects.create(
        name="integralmedica", display_name="Integralmedica"
    )

    # 5. Stores
    store_amazon = Store.objects.create(name="amazon", display_name="Amazon")
    store_ml = Store.objects.create(name="mercadolivre", display_name="Mercado Livre")
    store_growth = Store.objects.create(
        name="growth_official", display_name="Growth Oficial"
    )
    store_magalu = Store.objects.create(name="magalu", display_name="Magalu")

    # 6. Real Products Data
    # Format: (Brand, Name, Weight, Category, Serving(g), Protein(g), Carbs(g), Fats(g), PriceMin, PriceMax, [List of Tags], [List of Flavors])
    products_list = [
        # Growth
        (
            brand_growth,
            "Whey Protein Concentrado 80%",
            1000,
            cat_whey_conc,
            30,
            24,
            3.1,
            2.0,
            99.00,
            110.00,
            [tag_mass, tag_recovery, tag_gluten_free],
            ["Chocolate", "Morango", "Baunilha", "Natural", "Cookies & Cream"],
        ),
        (
            brand_growth,
            "Whey Protein Isolado 90%",
            1000,
            cat_whey_iso,
            30,
            27,
            0.5,
            0.5,
            144.00,
            160.00,
            [tag_mass, tag_weight_loss, tag_lactose_free, tag_gluten_free],
            ["Chocolate", "Morango", "Natural"],
        ),
        (
            brand_growth,
            "Creatina Monohidratada",
            250,
            cat_creatine,
            3,
            0,
            0,
            0,
            79.90,
            95.00,
            [tag_energy, tag_mass, tag_gluten_free, tag_vegan_tag],
            ["Sem Sabor"],
        ),
        # Max Titanium
        (
            brand_max,
            "Top Whey 3W Mais Performance",
            900,
            cat_whey_conc,
            40,
            31,
            5.4,
            2.1,
            140.00,
            180.00,
            [tag_mass, tag_recovery],
            ["Chocolate", "Morango", "Baunilha", "Limão"],
        ),
        (
            brand_max,
            "100% Whey",
            900,
            cat_whey_conc,
            30,
            20,
            4.5,
            1.8,
            110.00,
            140.00,
            [tag_mass],
            ["Chocolate", "Doce de Leite"],
        ),
        (
            brand_max,
            "Creatina",
            300,
            cat_creatine,
            3,
            0,
            0,
            0,
            80.00,
            110.00,
            [tag_mass, tag_energy],
            ["Sem Sabor"],
        ),
        # Dux
        (
            brand_dux,
            "Whey Protein Concentrado",
            900,
            cat_whey_conc,
            30,
            20,
            3.6,
            2.0,
            160.00,
            190.00,
            [tag_mass, tag_gluten_free],
            ["Chocolate", "Baunilha", "Cookies & Cream"],
        ),
        (
            brand_dux,
            "Whey Protein Isolado",
            900,
            cat_whey_iso,
            30,
            24,
            1.5,
            0.5,
            230.00,
            280.00,
            [tag_mass, tag_weight_loss, tag_lactose_free],
            ["Chocolate", "Baunilha"],
        ),
        # Integralmedica
        (
            brand_integral,
            "Whey 100% Pure",
            907,
            cat_whey_conc,
            30,
            20,
            4.3,
            1.9,
            100.00,
            130.00,
            [tag_mass, tag_recovery],
            ["Chocolate", "Morango", "Cookies & Cream"],
        ),
        (
            brand_integral,
            "Creatina Hardcore",
            300,
            cat_creatine,
            3,
            0,
            0,
            0,
            60.00,
            90.00,
            [tag_energy, tag_mass],
            ["Sem Sabor", "Uva"],
        ),
    ]

    for (
        brand,
        name,
        weight,
        category,
        serving,
        protein,
        carb,
        fat,
        p_min,
        p_max,
        tags,
        flavors,
    ) in products_list:
        # Create Product
        product = Product.objects.create(
            name=name,
            brand=brand,
            weight=weight,
            category=category,
            packaging=Product.Packaging.CONTAINER
            if weight > 500
            else Product.Packaging.OTHER,
        )

        # Add Tags
        product.tags.set(tags)

        # Create Nutrition Facts
        is_creatine = "creatina" in name.lower()
        if is_creatine:
            nutri_val = 3.0
            desc = "Creatina Pura"
        else:
            nutri_val = protein
            desc = f"Nutrição {name}"

        facts = NutritionFacts.objects.create(
            description=desc,
            serving_size_grams=serving,
            proteins=Decimal(str(nutri_val)),
            carbohydrates=Decimal(str(carb)),
            total_fats=Decimal(str(fat)),
            energy_kcal=int(serving * 4),  # approximate
            sodium=50,
        )

        # Product Nutrition Profile
        pn = ProductNutrition.objects.create(product=product, nutrition_facts=facts)

        # Add Flavors to Nutrition Profile
        valid_flavors = []
        for f_str in flavors:
            if f_str in flavor_objs:
                valid_flavors.append(flavor_objs[f_str])
            elif "Uva" in f_str:  # Handling flavors not in initial list dynamically
                new_f, _ = Flavor.objects.get_or_create(name=f_str)
                valid_flavors.append(new_f)

        if valid_flavors:
            pn.flavors.set(valid_flavors)

        # Create Links in Stores
        selected_stores = random.sample(
            [store_amazon, store_ml, store_magalu, store_growth], k=random.randint(2, 4)
        )

        for store in selected_stores:
            if store == store_growth and brand != brand_growth:
                continue

            link = ProductStore.objects.create(
                product=product,
                store=store,
                product_link=f"https://{store.name}.com/{product.id}",
                external_id=f"SKU-{random.randint(1000, 9999)}",
            )

            # Generate Price History (Last 30 days)
            current_price = float(p_max)
            now = timezone.now()

            num_points = random.randint(5, 12)
            for j in range(num_points):
                price_val = random.uniform(float(p_min), float(p_max))
                # Add some small trends
                if j % 2 == 0:
                    price_val += random.uniform(0, 5)

                day_offset = random.randint(0, 30)
                collected_time = now - timedelta(days=day_offset)

                ProductPriceHistory.objects.create(
                    store_product_link=link,
                    price=Decimal(f"{price_val:.2f}"),
                    collected_at=collected_time,
                    stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
                )

    print(
        f"✅ Successfully seeded {Product.objects.count()} products, {Tag.objects.count()} tags, {Flavor.objects.count()} flavors!"
    )


if __name__ == "__main__":
    run_seed()
