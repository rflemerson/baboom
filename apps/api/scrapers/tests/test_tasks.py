"""Tests for scraper task workflows and system checks."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from django.core.checks import run_checks
from django.test import TestCase
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from baboom.celery import app as celery_app
from scrapers.models import ScraperRun
from scrapers.tasks import EmptyMonitorRunError, _run_spider_monitor

if TYPE_CHECKING:
    from collections.abc import Iterator

from scrapers.tests import (
    EXPECTED_MONITOR_ITEMS,
    EXPECTED_SCRAPER_RUN_ITEMS,
    _raised,
)

EXPECTED_TIMEOUT_JOIN_CALLS = 2


@contextmanager
def _fake_crawl(stats: dict[str, object], exitcode: int = 0) -> Iterator[None]:
    """Stand in for the crawl child, writing the stats it would have written."""

    def build(target: object, args: tuple[str, str]) -> MagicMock:
        _ = target
        Path(args[1]).write_text(json.dumps(stats))
        return MagicMock(exitcode=exitcode, **{"is_alive.return_value": False})

    with patch("scrapers.tasks.multiprocessing.Process", side_effect=build):
        yield


@contextmanager
def _registry_without_scraper_tasks() -> Iterator[None]:
    """Put the process back in the state a non-worker starts in."""
    saved_tasks = dict(celery_app.tasks)
    saved_module = sys.modules.get("scrapers.tasks")
    for name in list(celery_app.tasks):
        if name.startswith("scrapers."):
            celery_app.tasks.pop(name)
    sys.modules.pop("scrapers.tasks", None)
    try:
        yield
    finally:
        if saved_module is not None:
            sys.modules["scrapers.tasks"] = saved_module
        celery_app.tasks.update(saved_tasks)


class ScraperRunHistoryTests(TestCase):
    """Tests for scraper monitor execution history."""

    def test_monitor_success_creates_scraper_run(self) -> None:
        """Successful monitor runs should be visible in admin history."""
        stats = {"item_scraped_count": 2, "downloader/request_count": 3}
        with _fake_crawl(stats):
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
        error = _raised(
            lambda: self._run_failing_crawl("Blocked Store"),
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

    def _run_failing_crawl(self, label: str) -> str:
        """Run the task helper against a child that exits with an error."""
        stats = {"last_error": "blocked by upstream"}
        with _fake_crawl(stats, exitcode=1):
            return _run_spider_monitor("test_store", label)

    def test_unrelated_error_log_does_not_fail_successful_crawl(self) -> None:
        """A library error line is not itself a failed spider."""
        with _fake_crawl({"item_scraped_count": 1, "log_count/ERROR": 1}):
            _run_spider_monitor("test_store", "Test Store")

        assert ScraperRun.objects.get().status == ScraperRun.Status.SUCCESS

    def test_non_finished_spider_reason_fails_the_run(self) -> None:
        """A premature Scrapy close is a failure even with exit status zero."""
        with _fake_crawl({"finish_reason": "closespider_timeout"}):
            _raised(
                lambda: _run_spider_monitor("test_store", "Test Store"),
                RuntimeError,
            )

        assert ScraperRun.objects.get().status == ScraperRun.Status.ERROR

    def test_stuck_child_is_terminated_and_run_is_closed(self) -> None:
        """A hung crawler cannot occupy the only worker indefinitely."""
        child = MagicMock(**{"is_alive.side_effect": [True, False]})
        with patch("scrapers.tasks.multiprocessing.Process", return_value=child):
            error = _raised(
                lambda: _run_spider_monitor("test_store", "Test Store"),
                TimeoutError,
            )

        assert "exceeded" in str(error)
        child.terminate.assert_called_once()
        assert child.join.call_count == EXPECTED_TIMEOUT_JOIN_CALLS
        run = ScraperRun.objects.get()
        assert run.status == ScraperRun.Status.ERROR
        assert "exceeded" in run.error_message

    def test_killed_child_never_gets_an_unbounded_join(self) -> None:
        """Even termination-resistant children cannot stall the worker forever."""
        child = MagicMock(**{"is_alive.side_effect": [True, True]})
        with patch("scrapers.tasks.multiprocessing.Process", return_value=child):
            _raised(
                lambda: _run_spider_monitor("test_store", "Test Store"),
                TimeoutError,
            )

        child.kill.assert_called_once()
        assert all(call.kwargs.get("timeout") for call in child.join.call_args_list)


class EmptyMonitorRunTests(TestCase):
    """An empty run is an error only for a monitor that used to produce items."""

    LABEL = "Dux"

    def _run(self, items: list[object]) -> str:
        """Run the monitor helper with a spider returning the given items."""
        stats = {"item_scraped_count": len(items), "downloader/request_count": 1}
        with _fake_crawl(stats):
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
