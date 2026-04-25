from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scrapers", "0008_scrapeditem_source_page_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scrapeditem",
            name="status",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("queued", "Queued for Agents"),
                    ("processing", "Processing"),
                    ("linked", "Linked"),
                    ("error", "Error (Retry)"),
                    ("discarded", "Discarded (Junk)"),
                    ("review", "Needs Review"),
                    ("ignored", "Ignored"),
                ],
                db_index=True,
                default="new",
                max_length=20,
            ),
        ),
    ]
