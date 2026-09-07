"""Rank actives per nutrition profile instead of per product."""

import django.db.models.deletion
from django.db import migrations, models


def clear_derived_rankings(apps, schema_editor):
    """Drop the per-product rows so the per-profile column can be added.

    These rows are derived from the nutrition profiles and carry nothing of
    their own, so they are rebuilt rather than remapped: run the
    ``sync_product_actives`` command once this migration has applied.
    """
    apps.get_model("core", "ProductActive").objects.all().delete()


class Migration(migrations.Migration):
    """Move the derived concentrations onto ProductNutrition."""

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            clear_derived_rankings,
            migrations.RunPython.noop,
        ),
        migrations.AlterModelOptions(
            name="productactive",
            options={
                "ordering": (
                    "nutrition_profile__product__name",
                    "nutrition_profile_id",
                    "active__name",
                ),
                "verbose_name": "Product Active",
                "verbose_name_plural": "Product Actives",
            },
        ),
        migrations.RemoveConstraint(
            model_name="productactive",
            name="unique_product_active",
        ),
        migrations.AddField(
            model_name="productactive",
            name="nutrition_profile",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="actives",
                to="core.productnutrition",
                verbose_name="Nutrition Profile",
            ),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="productactive",
            constraint=models.UniqueConstraint(
                fields=("nutrition_profile", "active"), name="unique_profile_active"
            ),
        ),
        migrations.RemoveField(
            model_name="productactive",
            name="product",
        ),
    ]
