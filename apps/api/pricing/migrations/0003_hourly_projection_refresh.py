"""Schedule an hourly refresh, so expired prices and promotions leave rankings."""

from django.db import migrations

TASK = "pricing.tasks.refresh_projections"


def schedule(apps, schema_editor):
    """Create the hourly beat entry, once."""
    _ = schema_editor
    interval = apps.get_model("django_celery_beat", "IntervalSchedule")
    periodic = apps.get_model("django_celery_beat", "PeriodicTask")
    every_hour, _created = interval.objects.get_or_create(every=1, period="hours")
    periodic.objects.get_or_create(
        name="Refresh pricing projections",
        defaults={"task": TASK, "interval": every_hour, "enabled": True},
    )


def unschedule(apps, schema_editor):
    """Remove the beat entry."""
    _ = schema_editor
    apps.get_model("django_celery_beat", "PeriodicTask").objects.filter(
        task=TASK,
    ).delete()


class Migration(migrations.Migration):
    """Add the hourly projection refresh."""

    dependencies = (
        ("pricing", "0002_default_policies"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    )

    operations = (migrations.RunPython(schedule, unschedule),)
