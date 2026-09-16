"""Tests for scraper task workflows."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from offers.models import Offer, StockStatus
from scrapers.models import ScraperRun
from scrapers.tasks import EmptyMonitorRunError, run_spider_monitor
from scrapers.tests.helpers import (
    EXPECTED_MONITOR_ITEMS,
    EXPECTED_SCRAPER_RUN_ITEMS,
    _raised,
)
from scrapers.tests.task_helpers import _fake_crawl

EXPECTED_TIMEOUT_JOIN_CALLS = 2


class ScraperRunHistoryTests(TestCase):
    """Tests for scraper monitor execution history."""

    def test_monitor_success_creates_scraper_run(self) -> None:
        """Successful monitor runs should be visible in admin history."""
        stats = {"item_scraped_count": 2, "downloader/request_count": 3}
        with _fake_crawl(stats):
            result = run_spider_monitor("test_store", "Test Store")
        run = ScraperRun.objects.get()

        assert result == (
            "Test Store Monitor: Saved/Updated 2 items, delisted 0. "
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
            return run_spider_monitor("test_store", label)

    def test_unrelated_error_log_does_not_fail_successful_crawl(self) -> None:
        """A library error line is not itself a failed spider."""
        with _fake_crawl({"item_scraped_count": 1, "log_count/ERROR": 1}):
            run_spider_monitor("test_store", "Test Store")

        assert ScraperRun.objects.get().status == ScraperRun.Status.SUCCESS

    def test_non_finished_spider_reason_fails_the_run(self) -> None:
        """A premature Scrapy close is a failure even with exit status zero."""
        with _fake_crawl({"finish_reason": "closespider_timeout"}):
            _raised(
                lambda: run_spider_monitor("test_store", "Test Store"),
                RuntimeError,
            )

        assert ScraperRun.objects.get().status == ScraperRun.Status.ERROR

    def test_stuck_child_is_terminated_and_run_is_closed(self) -> None:
        """A hung crawler cannot occupy the only worker indefinitely."""
        child = MagicMock(**{"is_alive.side_effect": [True, False]})
        with patch("scrapers.tasks.multiprocessing.Process", return_value=child):
            error = _raised(
                lambda: run_spider_monitor("test_store", "Test Store"),
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
                lambda: run_spider_monitor("test_store", "Test Store"),
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
            return run_spider_monitor("dux", self.LABEL)

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


class UnseenOfferDelistingTests(TestCase):
    """A unit the store stopped publishing leaves the catalog after repeated absence.

    This covers what per-page reconciliation cannot: a whole page that is gone,
    which is the only way a unit disappears on single-unit platforms.
    """

    LABEL = "Dark Lab"
    STORE = "dark_lab"

    def _offer(self, external_id: str, store: str = STORE) -> Offer:
        return Offer.objects.create(
            store_slug=store,
            external_id=external_id,
            pid=external_id,
            current_price=Decimal("99.90"),
        )

    def _run(
        self,
        *,
        seen: tuple[str, ...] = (),
        exitcode: int = 0,
        complete: bool = True,
    ) -> None:
        """Run the monitor, marking the given units as published by the store."""

        def build(target: object, args: tuple[str, str]) -> MagicMock:
            _ = target
            Offer.objects.filter(store_slug=self.STORE, external_id__in=seen).update(
                last_seen_at=timezone.now(),
                missed_runs=0,
                delisted_at=None,
            )
            Path(args[1]).write_text(
                json.dumps(
                    {
                        "item_scraped_count": 1,
                        "scraper/offers_collected": 1,
                        "scraper/store_slug": self.STORE,
                        "scraper/catalog_complete": complete,
                    },
                ),
            )
            return MagicMock(exitcode=exitcode, **{"is_alive.return_value": False})

        with patch("scrapers.tasks.multiprocessing.Process", side_effect=build):
            try:
                run_spider_monitor("dark_lab", self.LABEL)
            except RuntimeError:
                if exitcode == 0:
                    raise

    def test_one_absence_does_not_delist(self) -> None:
        """A single run that misses a unit may just have been incomplete."""
        self._offer("kept")
        self._offer("missing")

        self._run(seen=("kept",))

        missing = Offer.objects.get(external_id="missing")
        assert missing.delisted_at is None
        assert missing.missed_runs == 1

    def test_second_consecutive_absence_delists(self) -> None:
        """Two successful runs without the unit take it out of the catalog."""
        self._offer("kept")
        self._offer("missing")

        self._run(seen=("kept",))
        self._run(seen=("kept",))

        missing = Offer.objects.get(external_id="missing")
        assert missing.delisted_at is not None
        assert missing.current_price is None
        assert missing.current_stock_status == StockStatus.OUT_OF_STOCK
        assert Offer.objects.get(external_id="kept").delisted_at is None

    def test_a_failed_run_is_not_evidence_of_absence(self) -> None:
        """Only successful runs count; a failure between them changes nothing."""
        self._offer("kept")
        self._offer("missing")

        self._run(seen=("kept",))
        self._run(exitcode=1)

        missing = Offer.objects.get(external_id="missing")
        assert missing.delisted_at is None
        assert missing.missed_runs == 1

    def test_another_stores_offers_are_untouched(self) -> None:
        """A run speaks only for the store it crawled."""
        self._offer("kept")
        other = self._offer("elsewhere", store="growth")

        self._run(seen=("kept",))
        self._run(seen=("kept",))

        other.refresh_from_db()
        assert other.delisted_at is None
        assert other.missed_runs == 0

    def test_an_incomplete_crawl_never_delists(self) -> None:
        """A crawl that could not read the whole catalog proves no absence."""
        self._offer("kept")
        self._offer("missing")

        self._run(seen=("kept",), complete=False)
        self._run(seen=("kept",), complete=False)

        missing = Offer.objects.get(external_id="missing")
        assert missing.delisted_at is None
        assert missing.missed_runs == 0
