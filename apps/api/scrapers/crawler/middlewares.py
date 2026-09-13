"""Downloader policy for browser impersonation and soft WAF blocks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

from scrapy.downloadermiddlewares.retry import get_retry_request

# Scrapy itself imports the reactor at module scope, including in
# scrapy.utils.defer, which is loaded long before this middleware. The reactor
# chosen by TWISTED_REACTOR is already installed by the time a middleware runs.
from twisted.internet import reactor
from twisted.internet.task import deferLater

if TYPE_CHECKING:
    from scrapy import Request, Spider
    from scrapy.http import Response
    from twisted.internet.defer import Deferred

logger = logging.getLogger(__name__)

# scrapy_impersonate delegates the browser TLS fingerprint to curl_cffi.
HTTP_OK = 200
MAX_RETRY_AFTER_SECONDS = 120.0
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


def is_blocked(body: str) -> bool:
    """Return whether a response body is a known WAF challenge page."""
    return any(indicator in body for indicator in BLOCKED_INDICATORS)


class ImpersonationMiddleware:
    """Rotate TLS identities and retry status/WAF responses politely."""

    impersonations = IMPERSONATIONS

    def __init__(self) -> None:
        """Keep the rotation index per spider name, out of the spider itself."""
        self._indexes: dict[str, int] = {}

    def process_request(self, request: Request, spider: Spider) -> None:
        """Assign one stable browser identity to a new request."""
        if "impersonate" not in request.meta:
            request.meta["impersonate"] = self._current_identity(spider)

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
        retry.meta["impersonate"] = self._next_identity(spider)
        wait = parse_retry_after(response)
        if wait is None:
            return retry
        logger.info("Honoring Retry-After=%.1fs for %s", wait, request.url)
        return deferLater(reactor, wait, lambda: retry)

    def _current_identity(self, spider: Spider) -> str:
        """Return the identity currently assigned to this spider."""
        index = self._indexes.get(spider.name, 0)
        return self.impersonations[index % len(self.impersonations)]

    def _next_identity(self, spider: Spider) -> str:
        """Advance to the next identity after a block or refusal."""
        index = self._indexes.get(spider.name, 0) + 1
        self._indexes[spider.name] = index
        return self.impersonations[index % len(self.impersonations)]
