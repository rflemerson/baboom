"""Downloader policy: request identity (browser or signed bot) and WAF retries."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

from django.conf import settings
from scrapy.downloadermiddlewares.retry import get_retry_request

# Scrapy itself imports the reactor at module scope, including in
# scrapy.utils.defer, which is loaded long before this middleware. The reactor
# chosen by TWISTED_REACTOR is already installed by the time a middleware runs.
from twisted.internet import reactor
from twisted.internet.task import deferLater

from .web_bot_auth import load_private_key, request_headers

if TYPE_CHECKING:
    from scrapy import Request, Spider
    from scrapy.http import Response
    from twisted.internet.defer import Deferred

logger = logging.getLogger(__name__)

# scrapy_impersonate delegates the browser TLS fingerprint to curl_cffi.
HTTP_OK = 200
MAX_RETRY_AFTER_SECONDS = 120.0
# Shopify answers 429 with no Retry-After. Retrying at once spends every
# attempt in seconds; doubling from here spreads them over minutes.
RATE_LIMIT_BACKOFF_SECONDS = 30.0
HTTP_TOO_MANY_REQUESTS = 429
RETRYABLE_STATUS_CODES = frozenset({403, 429, 500, 502, 503, 504})
IMPERSONATIONS = ("chrome120", "chrome119", "chrome116", "safari17_0")

# These markers identify a challenge or denial page, not ordinary vendor
# scripts that happen to mention Cloudflare or Sucuri.
BLOCKED_INDICATORS = (
    "Sucuri WebSite Firewall",
    "sucuri-firewall-block",
    "Attention Required! | Cloudflare",
    "cf-browser-verification",
    "cf-challenge-running",
    "__cf_chl_",
    "Checking your browser before accessing",
    "Access Denied",
)


def parse_retry_after(
    response: Response,
    *,
    max_seconds: float = MAX_RETRY_AFTER_SECONDS,
) -> float | None:
    """Parse delta-seconds or an HTTP-date Retry-After header."""
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    if isinstance(raw, bytes):
        value = str(raw, encoding="latin-1").strip()
    else:
        value = str(raw).strip()
    if value.isdigit():
        return min(float(value), max_seconds)
    try:
        retry_at = parsedate_to_datetime(value)
    except TypeError, ValueError, OverflowError:
        return None
    if retry_at is None:
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    wait = (retry_at - datetime.now(UTC)).total_seconds()
    return min(wait, max_seconds) if wait > 0 else None


def rate_limit_backoff(attempt: int) -> float:
    """Return how long the given retry of a rate-limited request waits."""
    return min(
        RATE_LIMIT_BACKOFF_SECONDS * 2 ** max(attempt - 1, 0),
        MAX_RETRY_AFTER_SECONDS,
    )


def is_blocked(body: str) -> bool:
    """Return whether a response body is a known WAF challenge page."""
    return any(indicator in body for indicator in BLOCKED_INDICATORS)


class ImpersonationMiddleware:
    """Choose each request's identity and retry status/WAF responses politely.

    A spider with ``IDENTIFIES_ITSELF`` keeps its own User-Agent and signs
    every attempt (Web Bot Auth); the others rotate browser TLS identities.
    """

    impersonations = IMPERSONATIONS

    def __init__(self) -> None:
        """Keep the rotation index per spider name, out of the spider itself."""
        self._indexes: dict[str, int] = {}
        seed = settings.WEB_BOT_AUTH_PRIVATE_KEY
        self._key = load_private_key(seed) if seed else None

    def process_request(self, request: Request, spider: Spider) -> None:
        """Sign a self-identifying request, or give it a browser identity."""
        if self._disguised(spider):
            request.meta.setdefault("impersonate", self._current_identity(spider))
        elif self._key is not None:
            signed = request_headers(self._key, request.url, int(time.time()))
            for name, value in signed.items():
                request.headers[name] = value

    def process_response(
        self,
        request: Request,
        response: Response,
        spider: Spider,
    ) -> Response | Request | Deferred[Request]:
        """Retry forbidden, transient, and nominally successful WAF responses."""
        blocked_body = response.status == HTTP_OK and is_blocked(response.text)
        if response.status not in RETRYABLE_STATUS_CODES and not blocked_body:
            return response

        reason = "waf block page" if blocked_body else f"HTTP {response.status}"
        retry = get_retry_request(request, spider=spider, reason=reason)
        if retry is None:
            return response
        if self._disguised(spider):
            retry.meta["impersonate"] = self._next_identity(spider)
        wait = parse_retry_after(response)
        if wait is None and response.status == HTTP_TOO_MANY_REQUESTS:
            wait = rate_limit_backoff(int(retry.meta.get("retry_times", 1)))
        if wait is None:
            return retry
        logger.info("Waiting %.1fs before retrying %s", wait, request.url)
        return deferLater(reactor, wait, lambda: retry)

    @staticmethod
    def _disguised(spider: Spider) -> bool:
        """Tell whether the spider crawls as a browser instead of as itself."""
        return getattr(spider, "IDENTIFIES_ITSELF", False) is not True

    def _current_identity(self, spider: Spider) -> str:
        """Return the identity currently assigned to this spider."""
        index = self._indexes.get(spider.name, 0)
        return self.impersonations[index % len(self.impersonations)]

    def _next_identity(self, spider: Spider) -> str:
        """Advance to the next identity after a block or refusal."""
        index = self._indexes.get(spider.name, 0) + 1
        self._indexes[spider.name] = index
        return self.impersonations[index % len(self.impersonations)]
