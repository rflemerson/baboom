"""Django system checks for scraper infrastructure."""

from __future__ import annotations

from importlib import import_module

from django.core.checks import Warning as CheckWarning
from django.core.checks import register
from django.db import OperationalError, ProgrammingError


def _is_registered(task_name: str, celery_app: object) -> bool:
    """Whether a dotted task name resolves to a registered Celery task.

    Autodiscovery only runs in a worker, so outside one the registry starts
    empty and every entry would look orphaned. Importing the one module a name
    points at registers its tasks; importing every app's, as autodiscovery
    does, drags in far more than a check should touch.
    """
    if task_name in celery_app.tasks:
        return True
    module_path, _, _attribute = task_name.rpartition(".")
    if not module_path:
        return False
    try:
        import_module(module_path)
    except ImportError:
        return False
    return task_name in celery_app.tasks


@register()
def check_periodic_celery_tasks(
    app_configs: object,
    **kwargs: object,
) -> list[CheckWarning]:
    """Warn when an enabled beat entry points at no registered Celery task."""
    _ = app_configs, kwargs
    celery_app = import_module("baboom.celery").app
    periodic_task_model = import_module("django_celery_beat.models").PeriodicTask

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
            if not _is_registered(periodic.task, celery_app)
        ]
    except OperationalError, ProgrammingError:
        # The beat tables may not exist yet during a fresh install or migration.
        return []
