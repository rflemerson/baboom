"""Align existing rows with the kind discriminator and the nullable EAN."""

from django.db import migrations


def forwards(apps, schema_editor):
    """Mark assembled products as combos and free blank EAN values."""
    product = apps.get_model("core", "Product")
    product.objects.filter(component_links__isnull=False).distinct().update(
        kind="COMBO",
    )
    product.objects.filter(ean="").update(ean=None)


def backwards(apps, schema_editor):
    """Restore blank EAN values; the kind column is dropped by 0002."""
    product = apps.get_model("core", "Product")
    product.objects.filter(ean__isnull=True).update(ean="")


class Migration(migrations.Migration):
    """Data migration for the product kind rollout."""

    dependencies = [("core", "0002_product_kind_and_nullable_macros")]

    operations = [migrations.RunPython(forwards, backwards)]
