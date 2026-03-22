import json

from django.db import migrations, models


def forward_copy_scraped_page_context(apps, schema_editor):
    ScrapedPage = apps.get_model("scrapers", "ScrapedPage")

    for page in ScrapedPage.objects.all().iterator():
        raw_content = getattr(page, "raw_content", "") or ""
        parsed_context = {}
        if raw_content:
            try:
                parsed = json.loads(raw_content)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                parsed_context = parsed

        page.api_context = parsed_context
        page.html_structured_data = {}
        page.save(update_fields=["api_context", "html_structured_data"])


def reverse_copy_scraped_page_context(apps, schema_editor):
    ScrapedPage = apps.get_model("scrapers", "ScrapedPage")

    for page in ScrapedPage.objects.all().iterator():
        page.raw_content = json.dumps(
            getattr(page, "api_context", {}) or {},
            ensure_ascii=False,
        )
        page.content_type = "JSON"
        page.save(update_fields=["raw_content", "content_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("scrapers", "0004_delete_openfoodfactsdata_alter_scrapedpage_options"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="scrapedpage",
            options={"ordering": ("-scraped_at",)},
        ),
        migrations.AddField(
            model_name="scrapedpage",
            name="api_context",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Normalized product context collected from store APIs",
            ),
        ),
        migrations.AddField(
            model_name="scrapedpage",
            name="html_structured_data",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Structured metadata extracted from the product HTML",
            ),
        ),
        migrations.RunPython(
            forward_copy_scraped_page_context,
            reverse_copy_scraped_page_context,
        ),
        migrations.RemoveField(
            model_name="scrapedpage",
            name="raw_content",
        ),
        migrations.RemoveField(
            model_name="scrapedpage",
            name="content_type",
        ),
    ]
