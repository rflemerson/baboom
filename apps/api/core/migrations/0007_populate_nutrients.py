from django.db import migrations


def populate_nutrients(apps, schema_editor):
    Nutrient = apps.get_model("core", "Nutrient")

    # Macros
    macros = [
        {"name": "Protein", "slug": "protein", "is_macro": True},
        {"name": "Carbohydrates", "slug": "carbohydrates", "is_macro": True},
        {"name": "Fats", "slug": "fats", "is_macro": True},
    ]

    # Common Micros/Supplements
    micros = [
        {"name": "Creatine", "slug": "creatine", "is_macro": False},
        {"name": "Caffeine", "slug": "caffeine", "is_macro": False},
        {"name": "Vitamin C", "slug": "vitamin-c", "is_macro": False},
        {"name": "Omega 3", "slug": "omega-3", "is_macro": False},
        {"name": "Beta-Alanine", "slug": "beta-alanine", "is_macro": False},
        {"name": "Glutamine", "slug": "glutamine", "is_macro": False},
        {"name": "Pre-Workout Base", "slug": "pre-workout", "is_macro": False},
    ]

    for n in macros + micros:
        Nutrient.objects.get_or_create(
            slug=n["slug"],
            defaults={"name": n["name"], "is_macro": n["is_macro"]},
        )


def reverse_populate(apps, schema_editor):
    Nutrient = apps.get_model("core", "Nutrient")
    Nutrient.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_nutrient_historicalproduct_type_product_type_and_more"),
    ]

    operations = [
        migrations.RunPython(populate_nutrients, reverse_populate),
    ]
