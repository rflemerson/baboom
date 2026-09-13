"""Settings for the catalog Scrapy process."""

from __future__ import annotations

import importlib
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")

django_module = importlib.import_module("django")
django_module.setup()

BOT_NAME = "baboom-catalog"
SPIDER_MODULES = ["scrapers.crawler.spiders", "scrapers.stores"]
NEWSPIDER_MODULE = "scrapers.crawler.spiders"

CONCURRENT_REQUESTS_PER_DOMAIN = 2
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 60.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
DOWNLOAD_DELAY = 0.5
DOWNLOAD_DELAY_JITTER = 0.5

# ImpersonationMiddleware sits at 560, closer to the downloader than
# RetryMiddleware at 550, so it decides every retryable status itself and only
# RETRY_TIMES still applies. RETRY_HTTP_CODES would never be consulted.
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_PRIORITY_ADJUST = -1

# The old client did not consult robots.txt. Turning this on would change
# which products are collected and therefore needs an explicit product call.
ROBOTSTXT_OBEY = False
LOG_LEVEL = "INFO"

DOWNLOAD_HANDLERS = {
    "http": "scrapy_impersonate.ImpersonateDownloadHandler",
    "https": "scrapy_impersonate.ImpersonateDownloadHandler",
}
USER_AGENT = ""
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

DOWNLOADER_MIDDLEWARES = {
    "scrapers.crawler.middlewares.ImpersonationMiddleware": 560,
}
ITEM_PIPELINES = {
    "scrapers.crawler.pipelines.CatalogPipeline": 300,
}
EXTENSIONS = {
    "scrapers.crawler.extensions.StatsDumpExtension": 500,
}
SCRAPER_STATS_FILE = os.getenv("SCRAPER_STATS_FILE", "")
