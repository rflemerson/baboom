"""Base functionality shared by all scraper spiders."""

import logging
from random import choice, uniform
from time import sleep

CHROME_120_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CHROME_119_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
)
CHROME_116_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
)
SAFARI_17_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)

# Each User-Agent is paired with the curl_cffi TLS impersonation profile of the
# *same* browser version, so the JA3/TLS fingerprint stays consistent with the
# UA header. Mismatched pairs are an easy bot tell, so keep them aligned.
BROWSER_FINGERPRINTS = (
    (CHROME_120_UA, "chrome120"),
    (CHROME_119_UA, "chrome119"),
    (CHROME_116_UA, "chrome116"),
    (SAFARI_17_UA, "safari17_0"),
)


class BaseSpider:
    """Base class for all spiders."""

    user_agents = tuple(ua for ua, _ in BROWSER_FINGERPRINTS)
    browser_fingerprints = BROWSER_FINGERPRINTS

    FALLBACK_CATEGORIES: tuple[str, ...] = ()

    def __init__(self, categories: list[str] | None = None) -> None:
        """Initialize spider with optional category override."""
        self.categories_to_crawl = categories
        # One stable identity per run: a real browser keeps the same UA + TLS
        # fingerprint for the life of its session (which is also what keep-alive
        # connection reuse assumes). We only rotate to a fresh identity when a
        # request is blocked/throttled, via ``rotate_fingerprint``.
        self._fingerprint = self.pick_fingerprint()

    def pick_fingerprint(self) -> tuple[str, str]:
        """Return a random (User-Agent, TLS impersonation) pair, kept consistent."""
        return choice(self.browser_fingerprints)  # noqa: S311

    def rotate_fingerprint(self) -> tuple[str, str]:
        """Switch to a fresh (User-Agent, TLS impersonation) identity."""
        self._fingerprint = self.pick_fingerprint()
        return self._fingerprint

    @property
    def user_agent(self) -> str:
        """Current run User-Agent string."""
        return self._fingerprint[0]

    @property
    def impersonation(self) -> str:
        """Current run curl_cffi TLS impersonation profile."""
        return self._fingerprint[1]

    def get_headers(self) -> dict[str, str]:
        """Get default headers using the current run's stable browser identity."""
        return {
            "User-Agent": self.user_agent,
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
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
