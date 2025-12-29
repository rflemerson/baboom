"""
HTTP Client with WAF Bypass Support.

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
from typing import Any

logger = logging.getLogger(__name__)

# Try to import curl_cffi (preferred for WAF bypass)
try:
    from curl_cffi import requests as cffi_requests

    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    import requests as std_requests

    logger.warning(
        "curl_cffi not installed. WAF bypass may not work. "
        "Install with: pip install curl_cffi"
    )


class HttpClient:
    """
    HTTP Client with automatic WAF bypass using TLS fingerprint impersonation.
    Falls back to standard requests if curl_cffi is not available.
    """

    # Browser impersonations to try (in order of preference)
    IMPERSONATIONS = ["chrome120", "chrome119", "chrome116", "safari17_0"]

    def __init__(
        self,
        default_impersonate: str = "chrome120",
        timeout: int = 30,
    ):
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
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        verify: bool = True,
        impersonate: str | None = None,
        try_all_impersonations: bool = False,
    ) -> Any | None:
        """
        Perform GET request with WAF bypass.

        Args:
            url: URL to fetch
            headers: Request headers
            params: Query parameters
            verify: Verify SSL certificates
            impersonate: Browser to impersonate (chrome120, safari17_0, etc.)
            try_all_impersonations: If True, try all browser impersonations on failure

        Returns:
            Response object or None if all attempts failed
        """
        headers = headers or {}
        impersonate = impersonate or self.default_impersonate

        if HAS_CURL_CFFI:
            return self._get_with_curl_cffi(
                url, headers, params, verify, impersonate, try_all_impersonations
            )
        return self._get_with_requests(url, headers, params, verify)

    def _get_with_curl_cffi(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        verify: bool,
        impersonate: str,
        try_all: bool,
    ) -> Any | None:
        """Use curl_cffi with TLS fingerprint impersonation."""
        impersonations = self.IMPERSONATIONS if try_all else [impersonate]

        for browser in impersonations:
            try:
                logger.debug(f"Trying {browser} impersonation for: {url}")

                response = cffi_requests.get(
                    url,
                    headers=headers,
                    params=params,
                    impersonate=browser,
                    timeout=self.timeout,
                    verify=verify,
                )

                if response.status_code == 200 and not self._is_blocked(response.text):
                    logger.debug(f"Success with {browser}")
                    return response
                if response.status_code == 403:
                    logger.debug(f"{browser} blocked (403)")
                    continue
                # Return non-403 responses even if they might be errors
                return response

            except Exception as e:
                logger.debug(f"{browser} error: {e}")
                continue

        logger.warning(f"All impersonations failed for: {url}")
        return None

    def _get_with_requests(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        verify: bool,
    ) -> Any | None:
        """Fallback to standard requests library."""
        try:
            return std_requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
                verify=verify,
            )
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None


# Singleton instance for convenience
_default_client: HttpClient | None = None


def get_client() -> HttpClient:
    """Get or create the default HTTP client instance."""
    global _default_client
    if _default_client is None:
        _default_client = HttpClient()
    return _default_client
