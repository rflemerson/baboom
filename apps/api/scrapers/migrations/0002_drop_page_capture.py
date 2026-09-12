"""Drop the stored page capture.

The pass that filled these columns is gone: a curator opens the live page,
which is truer than a stored copy of it.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scrapers', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scrapedpage',
            name='html_structured_data',
        ),
        migrations.RemoveField(
            model_name='scrapedpage',
            name='raw_html',
        ),
        migrations.RemoveField(
            model_name='scrapedpage',
            name='response_meta',
        ),
    ]
