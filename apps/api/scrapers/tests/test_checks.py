"""Tests for scraper system checks."""

from __future__ import annotations

from django.core.checks import run_checks
from django.test import TestCase
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from scrapers.tests.task_helpers import _registry_without_scraper_tasks


class PeriodicTaskCheckTests(TestCase):
    """Beat entries must point at tasks registered by the Celery app."""

    def test_check_reports_enabled_orphaned_periodic_task(self) -> None:
        """The system check finds an enabled task missing from the registry."""
        interval, _created = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.create(
            name="Release Stuck Items",
            task="scrapers.tasks.release_stuck_items",
            enabled=True,
            interval=interval,
        )

        messages = run_checks()

        orphaned = [message for message in messages if message.id == "scrapers.W001"]
        assert len(orphaned) == 1
        assert "Release Stuck Items" in orphaned[0].msg
        assert "scrapers.tasks.release_stuck_items" in orphaned[0].msg

    def test_check_stays_quiet_for_a_task_whose_module_is_not_imported(self) -> None:
        """The production condition: an empty registry and an importable module.

        Outside a Celery worker nothing has imported the task modules, so the
        registry starts without them. The test process imports them itself,
        which is why the condition has to be staged here.
        """
        interval, _created = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.create(
            name="Scrape Dark Lab Monitor",
            task="scrapers.tasks.scrape_darklab_monitor",
            enabled=True,
            interval=interval,
        )

        with _registry_without_scraper_tasks():
            messages = run_checks()

        orphaned = [message for message in messages if message.id == "scrapers.W001"]
        assert orphaned == []
