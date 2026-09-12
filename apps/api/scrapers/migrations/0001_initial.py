"""Initial migration for the scraping pipeline models."""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """Initial schema for scraped pages, items and run history."""

    initial = True

    dependencies = [
        ('offers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScrapedPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('store_slug', models.CharField(db_index=True, help_text='Store identifier', max_length=100)),
                ('url', models.URLField(help_text='Page URL', max_length=500, unique=True)),
                ('api_context', models.JSONField(blank=True, default=dict, help_text='Normalized product context collected from store APIs')),
                ('html_structured_data', models.JSONField(blank=True, default=dict, help_text='Schema.org metadata (JSON-LD, microdata, ...) parsed from the HTML')),
                ('raw_html', models.TextField(blank=True, help_text='Full rendered product-page HTML — the capture source of truth')),
                ('response_meta', models.JSONField(blank=True, default=dict, help_text='HTTP response metadata for the capture (status, headers)')),
                ('scraped_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-scraped_at',),
            },
        ),
        migrations.CreateModel(
            name='ScrapedItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('offer', models.OneToOneField(help_text='Offer observed by the scraper', on_delete=django.db.models.deletion.CASCADE, related_name='scraped_item', to='offers.offer', verbose_name='Merchant Offer')),
                ('source_page', models.ForeignKey(blank=True, help_text='Source page where this item was found', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='items', to='scrapers.scrapedpage')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ScraperRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(db_index=True, max_length=100)),
                ('task_name', models.CharField(blank=True, db_index=True, max_length=255)),
                ('status', models.CharField(choices=[('running', 'Running'), ('success', 'Success'), ('error', 'Error')], db_index=True, default='running', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('duration_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('items_count', models.PositiveIntegerField(default=0)),
                ('message', models.CharField(blank=True, max_length=255)),
                ('error_message', models.TextField(blank=True)),
            ],
            options={
                'ordering': ('-started_at',),
                'indexes': [models.Index(fields=['label', '-started_at'], name='scrapers_sc_label_45cc2a_idx'), models.Index(fields=['status', '-started_at'], name='scrapers_sc_status_2c6a0a_idx')],
            },
        ),
    ]
