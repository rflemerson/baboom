"""HTTP client helpers with optional WAF bypass support.

This module provides a generic HTTP client that can bypass Sucuri WAF
and other bot protection systems using TLS fingerprint impersonation.

Usage:
    from scrapers.spiders.http_client import HttpClient

    client = HttpClient()
    response = client.get(url, headers=headers)

    if response:
        data = response.json()
"""

import functools
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

HTTP_SUCCESS_CODE = 200
HTTP_FORBIDDEN_CODE = 403

# Try to import curl_cffi (preferred for WAF bypass)
try:
    from curl_cffi import requests as cffi_requests

    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    import requests as std_requests

    logger.warning(
        "curl_cffi not installed. WAF bypass may not work. "
        "Install with: pip install curl_cffi",
    )


@dataclass(slots=True)
class HttpRequestOptions:
    """Options for a single HTTP GET request."""

    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, object] | None = None
    verify: bool = True
    impersonate: str | None = None
    try_all_impersonations: bool = False


class HttpClient:
    """HTTP Client with automatic WAF bypass using TLS fingerprint impersonation.

    Falls back to standard requests if curl_cffi is not available.
    """

    # Browser impersonations to try (in order of preference)
    IMPERSONATIONS = ("chrome120", "chrome119", "chrome116", "safari17_0")

    def __init__(
        self,
        default_impersonate: str = "chrome120",
        timeout: int = 30,
    ) -> None:
        """Initialize the HTTP client with a default browser fingerprint."""
        self.default_impersonate = default_impersonate
        self.timeout = timeout

    def _is_blocked(self, content: str) -> bool:
        """Check if response indicates WAF block."""
        blocked_indicators = [
            "Sucuri WebSite Firewall",
            "sucuri-firewall-block",
            "Access Denied",
            "Cloudflare",
            "cf-browser-verification",
        ]
        return any(indicator in content for indicator in blocked_indicators)

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

        if HAS_CURL_CFFI:
            return self._get_with_curl_cffi(
                url,
                options=HttpRequestOptions(
                    headers=headers,
                    params=resolved_options.params,
                    verify=resolved_options.verify,
                    impersonate=impersonate,
                    try_all_impersonations=resolved_options.try_all_impersonations,
                ),
            )
        return self._get_with_requests(
            url,
            options=HttpRequestOptions(
                headers=headers,
                params=resolved_options.params,
                verify=resolved_options.verify,
                impersonate=impersonate,
                try_all_impersonations=resolved_options.try_all_impersonations,
            ),
        )

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

        for browser in impersonations:
            try:
                logger.debug("Trying %s impersonation for: %s", browser, url)

                response = cffi_requests.get(
                    url,
                    headers=options.headers,
                    params=options.params,
                    impersonate=browser,
                    timeout=self.timeout,
                    verify=options.verify,
                )

                if response.status_code == HTTP_SUCCESS_CODE and not self._is_blocked(
                    response.text,
                ):
                    logger.debug("Success with %s", browser)
                    return response
                if response.status_code == HTTP_FORBIDDEN_CODE:
                    logger.debug("%s blocked (403)", browser)
                    continue
                # Return non-403 responses even if they might be errors.
                return response

            except cffi_requests.exceptions.RequestException as exc:
                logger.debug("%s error: %s", browser, exc)
                continue
            else:
                # Return non-403 responses even if they might be errors.
                return response

        logger.warning("All impersonations failed for: %s", url)
        return None

    def _get_with_requests(
        self,
        url: str,
        *,
        options: HttpRequestOptions,
    ) -> object | None:
        """Fallback to standard requests library."""
        try:
            return std_requests.get(
                url,
                headers=options.headers,
                params=options.params,
                timeout=self.timeout,
                verify=options.verify,
            )
        except std_requests.exceptions.RequestException:
            logger.exception("Request failed")
            return None


# Singleton instance for convenience


@functools.lru_cache(maxsize=1)
def get_client() -> HttpClient:
    """Get or create the default HTTP client instance."""
    return HttpClient()
