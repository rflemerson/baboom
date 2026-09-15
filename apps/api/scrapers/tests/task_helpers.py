"""Shared task-test helpers."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from baboom.celery import app as celery_app

if TYPE_CHECKING:
    from collections.abc import Iterator


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
