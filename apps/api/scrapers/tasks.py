"""Celery tasks for running scraper monitors and recovery jobs."""

from __future__ import annotations

import json
import multiprocessing
import tempfile
from pathlib import Path

from celery import shared_task
from celery._state import get_current_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .crawler.run import crawl
from .models import ScraperRun
from .services import ScraperService

logger = get_task_logger(__name__)
CRAWL_TIMEOUT_SECONDS = 1800
TERMINATION_GRACE_SECONDS = 5


class EmptyMonitorRunError(RuntimeError):
    """A monitor that used to return products returned none."""


def _raise_crawl_timeout(label: str) -> None:
    """Report the hard wall-clock limit after the child has been stopped."""
    message = f"{label} crawl exceeded {CRAWL_TIMEOUT_SECONDS} seconds."
    raise TimeoutError(message)


def _monitor_has_produced_items(label: str) -> bool:
    """Whether this monitor ever completed a run carrying products.

    The expectation comes from the store's own history rather than a tuned
    threshold: a monitor that has produced items and now returns none is
    pointing at something that changed, while a brand new store legitimately
    starts empty.
    """
    return ScraperRun.objects.filter(
        label=label,
        status=ScraperRun.Status.SUCCESS,
        items_count__gt=0,
    ).exists()


def _finish_run(
    run: ScraperRun,
    *,
    status: str,
    message: str,
    items_count: int = 0,
    error_message: str = "",
) -> None:
    """Close a scraper run record with its outcome."""
    finished_at = timezone.now()
    run.status = status
    run.finished_at = finished_at
    run.duration_ms = int((finished_at - run.started_at).total_seconds() * 1000)
    run.items_count = items_count
    run.message = message
    run.error_message = error_message
    run.save(
        update_fields=(
            "status",
            "finished_at",
            "duration_ms",
            "items_count",
            "message",
            "error_message",
        ),
    )


def _read_scrapy_stats(path: Path) -> dict[str, object]:
    """Read the stats written by the Scrapy subprocess, if available."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError, TypeError, ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _stat_int(stats: dict[str, object], key: str) -> int:
    """Read an integer Scrapy stat without trusting subprocess output."""
    try:
        return int(stats.get(key, 0) or 0)
    except TypeError, ValueError, OverflowError:
        return 0


def _cleanup_stats_file(path: Path | None) -> None:
    """Remove the temporary stats file after the run has been recorded."""
    if path is not None:
        path.unlink(missing_ok=True)


def _delist_unseen_offers(stats: dict[str, object], run: ScraperRun) -> int:
    """Let a successful run count the units its store no longer publishes."""
    store_slug = str(stats.get("scraper/store_slug") or "")
    if not store_slug:
        return 0
    return ScraperService.delist_unseen_offers(store_slug, run.started_at)


def _run_spider_monitor(spider_name: str, label: str) -> str:
    """Run one Scrapy spider in a child process and record its outcome.

    The crawl needs its own process because the Twisted reactor cannot be
    restarted, and the worker runs several crawls a day.
    """
    current_task = get_current_task()
    run = ScraperRun.objects.create(
        label=label,
        task_name=current_task.name if current_task else "",
    )
    logger.info("Starting %s monitor task", label)
    stats_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix=f"{spider_name}-stats-",
            suffix=".json",
            delete=False,
        ) as stats_file:
            stats_path = Path(stats_file.name)
        child = multiprocessing.Process(
            target=crawl,
            args=(spider_name, str(stats_path)),
        )
        child.start()
        child.join(timeout=CRAWL_TIMEOUT_SECONDS)
        if child.is_alive():
            child.terminate()
            child.join(timeout=TERMINATION_GRACE_SECONDS)
            if child.is_alive():
                child.kill()
                child.join(timeout=TERMINATION_GRACE_SECONDS)
            _raise_crawl_timeout(label)
        exit_code = child.exitcode
    except Exception as exc:
        _cleanup_stats_file(stats_path)
        _finish_run(
            run,
            status=ScraperRun.Status.ERROR,
            message=f"{label} Monitor failed.",
            error_message=str(exc),
        )
        logger.exception("%s monitor task failed", label)
        raise

    stats = _read_scrapy_stats(stats_path) if stats_path else {}
    item_pages = _stat_int(stats, "item_scraped_count")
    items_count = _stat_int(stats, "scraper/offers_collected") or item_pages
    requests_count = _stat_int(stats, "downloader/request_count")
    responses_count = _stat_int(stats, "downloader/response_count")
    finish_reason = str(stats.get("finish_reason") or "finished")
    stats_summary = (
        f" Scrapy: {requests_count} requests, {responses_count} responses, "
        f"{item_pages} pages."
    )

    if exit_code != 0 or finish_reason != "finished":
        error_message = str(stats.get("last_error") or "").strip() or (
            f"The crawl process exited with status {exit_code}."
            if exit_code != 0
            else f"Scrapy closed with reason {finish_reason}."
        )
        _finish_run(
            run,
            status=ScraperRun.Status.ERROR,
            message=f"{label} Monitor failed.",
            items_count=items_count,
            error_message=error_message,
        )
        _cleanup_stats_file(stats_path)
        logger.error("%s monitor task failed: %s", label, error_message)
        raise RuntimeError(error_message)

    if not items_count and _monitor_has_produced_items(label):
        message = (
            f"{label} Monitor returned no products, but previous runs did. "
            f"The store layout or endpoint has most likely changed."
        )
        _finish_run(
            run,
            status=ScraperRun.Status.ERROR,
            message=f"{label} Monitor returned no products.",
            error_message=message,
        )
        _cleanup_stats_file(stats_path)
        logger.error(message)
        raise EmptyMonitorRunError(message)

    delisted = _delist_unseen_offers(stats, run)
    message = (
        f"{label} Monitor: Saved/Updated {items_count} items, "
        f"delisted {delisted}.{stats_summary}"
    )
    _finish_run(
        run,
        status=ScraperRun.Status.SUCCESS,
        message=message,
        items_count=items_count,
    )
    _cleanup_stats_file(stats_path)
    logger.info(message)
    return message


@shared_task
def scrape_growth_monitor() -> str:
    """Scrape Growth Supplements via API."""
    return _run_spider_monitor("growth", "Growth")


@shared_task
def scrape_blackskull_monitor() -> str:
    """Scrape Black Skull via API."""
    return _run_spider_monitor("blackskull", "Black Skull")


@shared_task
def scrape_integral_monitor() -> str:
    """Scrape Integral Medica."""
    return _run_spider_monitor("integral_medica", "Integral Medica")


@shared_task
def scrape_maxtitanium_monitor() -> str:
    """Scrape Max Titanium."""
    return _run_spider_monitor("max_titanium", "Max Titanium")


@shared_task
def scrape_probiotica_monitor() -> str:
    """Scrape Probiotica."""
    return _run_spider_monitor("probiotica", "Probiotica")


@shared_task
def scrape_darklab_monitor() -> str:
    """Scrape Dark Lab."""
    return _run_spider_monitor("dark_lab", "Dark Lab")


@shared_task
def scrape_dux_monitor() -> str:
    """Scrape Dux Nutrition."""
    return _run_spider_monitor("dux", "Dux")


@shared_task
def scrape_soldiers_monitor() -> str:
    """Scrape Soldiers Nutrition."""
    return _run_spider_monitor("soldiers", "Soldiers")
