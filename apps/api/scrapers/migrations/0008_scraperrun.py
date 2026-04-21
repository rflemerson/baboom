# Generated manually to add auditable scraper execution history.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scrapers", "0007_scrapeditemextraction_approved_at_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScraperRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("label", models.CharField(db_index=True, max_length=100)),
                (
                    "task_name",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("success", "Success"),
                            ("error", "Error"),
                        ],
                        db_index=True,
                        default="running",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("items_count", models.PositiveIntegerField(default=0)),
                ("message", models.CharField(blank=True, max_length=255)),
                ("error_message", models.TextField(blank=True)),
            ],
            options={
                "ordering": ("-started_at",),
                "indexes": [
                    models.Index(
                        fields=["label", "-started_at"],
                        name="scrapers_sc_label_45cc2a_idx",
                    ),
                    models.Index(
                        fields=["status", "-started_at"],
                        name="scrapers_sc_status_2c6a0a_idx",
                    ),
                ],
            },
        ),
    ]
