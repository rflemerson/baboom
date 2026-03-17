"""Base functionality shared by all scraper spiders."""

import logging
from random import uniform
from time import sleep

WINDOWS_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
MAC_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
)
LINUX_CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36"
)


class BaseSpider:
    """Base class for all spiders."""

    user_agents = (
        WINDOWS_CHROME_UA,
        MAC_CHROME_UA,
        LINUX_CHROME_UA,
    )

    FALLBACK_CATEGORIES: tuple[str, ...] = ()

    def __init__(self, categories: list[str] | None = None) -> None:
        """Initialize spider with optional category override."""
        self.categories_to_crawl = categories

    def get_headers(self) -> dict[str, str]:
        """Get default headers."""
        return {
            "User-Agent": self.user_agents[0],  # Simple rotation logic for now
            "Accept-Language": "en-US,en;q=0.9",
        }

    logger = logging.getLogger(__name__)

    def sleep_random(self, min_seconds: float = 1, max_seconds: float = 3) -> None:
        """Sleep for a random duration."""
        sleep(uniform(min_seconds, max_seconds))  # noqa: S311

    def check_category_discrepancy(
        self,
        dynamic_categories: list[str],
        fallback_categories: list[str],
    ) -> None:
        """Compare dynamic categories with fallback categories and log warnings."""
        if not dynamic_categories or not fallback_categories:
            return

        dynamic_set = set(dynamic_categories)
        fallback_set = set(fallback_categories)

        missing = fallback_set - dynamic_set
        extra = dynamic_set - fallback_set

        if missing:
            self.logger.warning(
                "[%s] Categories in FALLBACK but not in Dynamic: %s",
                self.__class__.__name__,
                missing,
            )
        if extra:
            self.logger.warning(
                "[%s] Categories in Dynamic but not in FALLBACK: %s",
                self.__class__.__name__,
                extra,
            )
