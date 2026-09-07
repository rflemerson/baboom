"""HTTP client helpers with WAF bypass support.

This module provides a generic HTTP client that can bypass Sucuri WAF
and other bot protection systems using TLS fingerprint impersonation.

Usage:
    from scrapers.spiders.http_client import HttpClient

    client = HttpClient()
    response = client.get(url, headers=headers)

    if response:
        data = response.json()
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC
from email.utils import parsedate_to_datetime

from curl_cffi import requests as cffi_requests
from django.utils import timezone

logger = logging.getLogger(__name__)

HTTP_SUCCESS_CODE = 200
HTTP_FORBIDDEN_CODE = 403

# Transient statuses worth retrying with backoff (rate limit / gateway errors).
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
# Never honor a server-provided Retry-After longer than this (seconds), so a
# hostile or misconfigured header cannot park a worker for minutes/hours.
MAX_RETRY_AFTER_SECONDS = 120.0


def parse_retry_after(
    response: object,
    *,
    max_seconds: float = MAX_RETRY_AFTER_SECONDS,
) -> float | None:
    """Return the wait in seconds requested by a ``Retry-After`` header, if any.

    Handles both the delta-seconds form (``Retry-After: 120``) and the HTTP-date
    form (``Retry-After: Wed, 21 Oct 2025 07:28:00 GMT``). Honoring this header
    is the politest possible response to a 429/503 and avoids escalation. The
    value is clamped to ``max_seconds`` so a bad header cannot stall a worker.
    """
    wait: float | None = None
    headers = getattr(response, "headers", None)
    raw = headers.get("Retry-After") or headers.get("retry-after") if headers else None
    if raw:
        raw = str(raw).strip()
    if raw and raw.isdigit():
        wait = min(float(raw), max_seconds)
    elif raw:
        wait = _parse_retry_after_date(raw, max_seconds=max_seconds)
    return wait


def _parse_retry_after_date(raw: str, *, max_seconds: float) -> float | None:
    """Return seconds until an HTTP-date Retry-After value, if valid."""
    try:
        retry_at = parsedate_to_datetime(raw)
    except TypeError, ValueError:
        return None
    if retry_at is None:
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    delta = (retry_at - timezone.now()).total_seconds()
    if delta <= 0:
        return None
    return min(delta, max_seconds)


@dataclass(slots=True)
class HttpRequestOptions:
    """Options for a single HTTP GET request."""

    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, object] | None = None
    verify: bool = True
    impersonate: str | None = None
    try_all_impersonations: bool = False
    timeout: int | None = None


#: Markers of an actual challenge or denial page served with a 200 status.
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


class HttpClient:
    """HTTP Client with automatic WAF bypass using TLS fingerprint impersonation."""

    # Browser impersonations to try (in order of preference)
    IMPERSONATIONS = ("chrome120", "chrome119", "chrome116", "safari17_0")

    def __init__(
        self,
        default_impersonate: str = "chrome120",
        timeout: int = 30,
    ) -> None:
        """Initialize the HTTP client with a default browser fingerprint.

        A single ``Session`` is reused for the client's lifetime so connections
        to the same host are kept alive (TCP/TLS reuse, HTTP/2 multiplexing).
        Besides being faster, reusing one connection per identity is what a real
        browser does, so it reads as less robotic.
        """
        self.default_impersonate = default_impersonate
        self.timeout = timeout
        self._session = cffi_requests.Session()

    def is_blocked(self, content: str) -> bool:
        """Check if a nominally successful response is really a WAF block page.

        The markers must identify a challenge or denial page, never the mere
        presence of a vendor name: stores legitimately ship Cloudflare analytics
        and CDN scripts, and matching the bare word discards a good catalog page.
        """
        return any(indicator in content for indicator in BLOCKED_INDICATORS)

    def _is_blocked_response(self, response: object) -> bool:
        """Return whether a nominally successful response is a WAF block page."""
        return response.status_code == HTTP_SUCCESS_CODE and self.is_blocked(
            str(getattr(response, "text", "")),
        )

    def get(
        self,
        url: str,
        *,
        options: HttpRequestOptions | None = None,
    ) -> object | None:
        """Perform GET request with WAF bypass.

        Args:
            url: URL to fetch
            options: Named request options including headers, params, SSL
                verification, and impersonation strategy.

        Returns:
            Response object or None if all attempts failed

        """
        resolved_options = options or HttpRequestOptions()
        headers = resolved_options.headers
        impersonate = resolved_options.impersonate or self.default_impersonate

        normalized = HttpRequestOptions(
            headers=headers,
            params=resolved_options.params,
            verify=resolved_options.verify,
            impersonate=impersonate,
            try_all_impersonations=resolved_options.try_all_impersonations,
            timeout=resolved_options.timeout,
        )
        return self._get_with_curl_cffi(url, options=normalized)

    def _get_with_curl_cffi(
        self,
        url: str,
        *,
        options: HttpRequestOptions,
    ) -> object | None:
        """Use curl_cffi with TLS fingerprint impersonation."""
        impersonate = options.impersonate or self.default_impersonate
        impersonations = (
            self.IMPERSONATIONS if options.try_all_impersonations else [impersonate]
        )
        timeout = options.timeout or self.timeout

        for browser in impersonations:
            try:
                logger.debug("Trying %s impersonation for: %s", browser, url)

                response = self._session.get(
                    url,
                    headers=options.headers,
                    params=options.params,
                    impersonate=browser,
                    timeout=timeout,
                    verify=options.verify,
                )

                if response.status_code == HTTP_SUCCESS_CODE:
                    if self._is_blocked_response(response):
                        logger.debug("%s returned a WAF block page", browser)
                        continue
                    logger.debug("Success with %s", browser)
                    return response

            except cffi_requests.exceptions.RequestException as exc:
                logger.debug("%s error: %s", browser, exc)
                continue

            if response.status_code == HTTP_FORBIDDEN_CODE:
                logger.debug("%s blocked (403)", browser)
                continue
            # Return non-403 responses even if they might be errors.
            return response

        logger.warning("All impersonations failed for: %s", url)
        return None
