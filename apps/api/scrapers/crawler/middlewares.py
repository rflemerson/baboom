"""Downloader policy for browser impersonation and soft WAF blocks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from scrapy import Request
from scrapy.http import Response
from scrapy.downloadermiddlewares.retry import get_retry_request

logger = logging.getLogger(__name__)

# scrapy_impersonate delegates the browser TLS fingerprint to curl_cffi.
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
    value = str(raw, encoding="latin-1").strip() if isinstance(raw, bytes) else str(raw).strip()
    if value.isdigit():
        return min(float(value), max_seconds)
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
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

    def process_request(self, request: Request, spider: object) -> None:
        """Assign one stable browser identity to a new request."""
        if "impersonate" not in request.meta:
            request.meta["impersonate"] = self._current_identity(spider)

    def process_response(self, request: Request, response: Response, spider: object):
        """Retry forbidden, transient, and nominally successful WAF responses."""
        blocked_body = response.status == 200 and is_blocked(response.text)
        if response.status not in RETRYABLE_STATUS_CODES and not blocked_body:
            return response

        reason = "waf block page" if blocked_body else f"HTTP {response.status}"
        retry = get_retry_request(request, spider=spider, reason=reason)
        if retry is None:
            return response
        retry.meta["impersonate"] = self._next_identity(spider)
        wait = parse_retry_after(response)
        if wait is not None:
            logger.info("Honoring Retry-After=%.1fs for %s", wait, request.url)
            return self._delayed(wait, retry)
        return retry

    def _delayed(self, wait: float, retry: Request):
        """Import the reactor lazily: importing it early installs the wrong one."""
        from twisted.internet import reactor
        from twisted.internet.task import deferLater

        return deferLater(reactor, wait, lambda: retry)

    def _current_identity(self, spider: object) -> str:
        index = int(getattr(spider, "_impersonation_index", 0))
        return self.impersonations[index % len(self.impersonations)]

    def _next_identity(self, spider: object) -> str:
        index = int(getattr(spider, "_impersonation_index", 0)) + 1
        spider._impersonation_index = index
        return self.impersonations[index % len(self.impersonations)]
