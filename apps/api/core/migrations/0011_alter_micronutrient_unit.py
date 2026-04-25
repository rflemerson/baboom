from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_remove_product_nutrient_sources_alter_brand_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="micronutrient",
            name="unit",
            field=models.CharField(
                choices=[
                    ("-", "-"),
                    ("g", "g"),
                    ("mg", "mg"),
                    ("mcg", "mcg"),
                    ("IU", "IU"),
                    ("%", "%"),
                ],
                default="-",
                max_length=10,
                verbose_name="Unit",
            ),
        ),
    ]
