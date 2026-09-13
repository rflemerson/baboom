"""Child-process entry point for one crawl.

This module must not import Django models: the forkserver child imports it
while unpickling the target, before Django has been set up.
"""

from __future__ import annotations

import os
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

API_ROOT = Path(__file__).resolve().parents[2]


def crawl(spider_name: str, stats_path: str) -> None:
    """Run one spider to completion in this process."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
    os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "scrapers.crawler.settings")
    os.environ["SCRAPER_STATS_FILE"] = stats_path
    os.chdir(API_ROOT)

    process = CrawlerProcess(get_project_settings())
    process.crawl(spider_name)
    process.start()
