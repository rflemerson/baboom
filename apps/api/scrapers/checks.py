"""Django system checks for scraper infrastructure."""

from __future__ import annotations

from importlib import import_module

from django.core.checks import Warning as CheckWarning
from django.core.checks import register
from django.db import OperationalError, ProgrammingError


@register()
def check_periodic_celery_tasks(
    app_configs: object,
    **kwargs: object,
) -> list[CheckWarning]:
    """Warn when an enabled beat entry points at no registered Celery task."""
    _ = app_configs, kwargs
    celery_app = import_module("baboom.celery").app
    periodic_task_model = import_module("django_celery_beat.models").PeriodicTask

    registered_tasks = set(celery_app.tasks)
    try:
        periodic_tasks = periodic_task_model.objects.filter(enabled=True).only(
            "name",
            "task",
        )
        return [
            CheckWarning(
                f"Enabled periodic task {periodic.name!r} points to "
                f"unregistered Celery task {periodic.task!r}.",
                hint="Disable or remove the orphaned PeriodicTask entry.",
                obj=periodic,
                id="scrapers.W001",
            )
            for periodic in periodic_tasks
            if periodic.task not in registered_tasks
        ]
    except OperationalError, ProgrammingError:
        # The beat tables may not exist yet during a fresh install or migration.
        return []
