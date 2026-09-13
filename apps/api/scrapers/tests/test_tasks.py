"""Tests for scraper task workflows and system checks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.checks import run_checks
from django.test import TestCase
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from scrapers.models import ScraperRun
from scrapers.tasks import EmptyMonitorRunError, _run_spider_monitor
from scrapers.tests import (
    EXPECTED_MONITOR_ITEMS,
    EXPECTED_SCRAPER_RUN_ITEMS,
    _raised,
)


class ScraperRunHistoryTests(TestCase):
    """Tests for scraper monitor execution history."""

    def test_monitor_success_creates_scraper_run(self) -> None:
        """Successful monitor runs should be visible in admin history."""

        def fake_run(_command: list[str], **kwargs: object) -> object:
            Path(kwargs["env"]["SCRAPER_STATS_FILE"]).write_text(
                json.dumps({"item_scraped_count": 2, "downloader/request_count": 3}),
            )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("scrapers.tasks.subprocess.run", side_effect=fake_run):
            result = _run_spider_monitor("test_store", "Test Store")
        run = ScraperRun.objects.get()

        assert result == (
            "Test Store Monitor: Saved/Updated 2 items. "
            "Scrapy: 3 requests, 0 responses, 2 pages."
        )
        assert run.label == "Test Store"
        assert run.status == ScraperRun.Status.SUCCESS
        assert run.items_count == EXPECTED_SCRAPER_RUN_ITEMS
        assert run.finished_at is not None
        assert run.duration_ms is not None
        assert run.error_message == ""

    def test_monitor_error_creates_failed_scraper_run(self) -> None:
        """Failed monitor runs should record the error before re-raising."""

        def fake_run(_command: list[str], **_kwargs: object) -> object:
            return MagicMock(returncode=1, stdout="", stderr="blocked by upstream")

        error = _raised(
            lambda: self._run_subprocess(fake_run, "Blocked Store"),
            RuntimeError,
        )

        assert str(error) == "blocked by upstream"

        run = ScraperRun.objects.get()
        assert run.label == "Blocked Store"
        assert run.status == ScraperRun.Status.ERROR
        assert run.items_count == 0
        assert run.finished_at is not None
        assert run.duration_ms is not None
        assert run.message == "Blocked Store Monitor failed."
        assert run.error_message == "blocked by upstream"

    def _run_subprocess(self, runner: object, label: str) -> str:
        """Run the task helper with a fake subprocess."""
        with patch("scrapers.tasks.subprocess.run", side_effect=runner):
            return _run_spider_monitor("test_store", label)


class EmptyMonitorRunTests(TestCase):
    """An empty run is an error only for a monitor that used to produce items."""

    LABEL = "Dux"

    def _run(self, items: list[object]) -> str:
        """Run the monitor helper with a spider returning the given items."""

        def fake_run(_command: list[str], **kwargs: object) -> object:
            Path(kwargs["env"]["SCRAPER_STATS_FILE"]).write_text(
                json.dumps(
                    {"item_scraped_count": len(items), "downloader/request_count": 1}
                ),
            )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("scrapers.tasks.subprocess.run", side_effect=fake_run):
            return _run_spider_monitor("dux", self.LABEL)

    def test_empty_run_is_success_for_a_monitor_without_history(self) -> None:
        """A store that never produced items may legitimately return none."""
        message = self._run([])

        run = ScraperRun.objects.get()
        assert run.status == ScraperRun.Status.SUCCESS
        assert run.items_count == 0
        assert "0 items" in message

    def test_empty_run_fails_after_the_monitor_has_produced_items(self) -> None:
        """Going silently to zero is what hid the Dux and Integral breakages."""
        ScraperRun.objects.create(
            label=self.LABEL,
            status=ScraperRun.Status.SUCCESS,
            items_count=112,
        )

        _raised(lambda: self._run([]), EmptyMonitorRunError)

        run = ScraperRun.objects.filter(items_count=0).get()
        assert run.status == ScraperRun.Status.ERROR
        assert "most likely changed" in run.error_message

    def test_empty_run_of_another_monitor_does_not_raise(self) -> None:
        """History is per monitor, so a healthy store does not fail its peer."""
        ScraperRun.objects.create(
            label="Growth",
            status=ScraperRun.Status.SUCCESS,
            items_count=199,
        )

        self._run([])

        run = ScraperRun.objects.get(label=self.LABEL)
        assert run.status == ScraperRun.Status.SUCCESS

    def test_run_with_items_records_success(self) -> None:
        """The normal path still records the item count."""
        self._run([object(), object()])

        run = ScraperRun.objects.get()
        assert run.status == ScraperRun.Status.SUCCESS
        assert run.items_count == EXPECTED_MONITOR_ITEMS

    def test_scrapy_stats_and_empty_monitor_rule_are_recorded(self) -> None:
        """Scrapy item stats feed the run and an empty first run is allowed."""
        message = self._run([])
        run = ScraperRun.objects.get()
        assert run.status == ScraperRun.Status.SUCCESS
        assert "Scrapy: 1 requests, 0 responses, 0 pages." in message


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
