"""Remove nutrition facts content hash deduplication."""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove the hash field from nutrition facts."""

    dependencies = [
        ("core", "0008_remove_productnutrition_component_weight_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="nutritionfacts",
            name="content_hash",
        ),
    ]
