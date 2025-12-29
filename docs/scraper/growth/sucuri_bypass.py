"""
Sucuri WAF Bypass Module for Growth Supplements (gsuplementos.com.br)

This module provides two levels of bypass:
- Level 1: curl_cffi (impersonates Chrome's TLS fingerprint)
- Level 2: Playwright (full browser automation for captcha bypass)

Usage:
    from sucuri_bypass import get_with_bypass
    response = get_with_bypass(url)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Try to import curl_cffi first (Level 1)
try:
    from curl_cffi import requests as cffi_requests

    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    logger.warning("curl_cffi not installed. Level 1 bypass unavailable.")

# Try to import Playwright (Level 2)
try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("playwright not installed. Level 2 bypass unavailable.")


class SucuriBypass:
    """Handles Sucuri WAF bypass for Growth Supplements."""

    BASE_URL = "https://www.gsuplementos.com.br"
    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="120", "Google Chrome";v="120", "Not_A Brand";v="8"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Linux"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    def __init__(self):
        self.session = None

    def _is_blocked(self, content: str) -> bool:
        """Check if response indicates Sucuri block."""
        return "Sucuri WebSite Firewall" in content or "sucuri-firewall-block" in content

    def get_with_curl_cffi(self, url: str) -> dict[str, Any] | None:
        """
        Level 1: Use curl_cffi to impersonate Chrome's TLS fingerprint.
        This often bypasses Sucuri without needing to click anything.
        """
        if not HAS_CURL_CFFI:
            logger.error("curl_cffi not available")
            return None

        # Try multiple browser impersonations
        impersonations = ["chrome120", "chrome119", "chrome116", "safari17_0"]
        
        # Headers specifically for Growth API
        api_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "app-token": "wapstore",  # Critical for Growth API
            "Content-Type": "application/json",
            "Origin": "https://www.gsuplementos.com.br",
            "Referer": "https://www.gsuplementos.com.br/",
            "Sec-Ch-Ua": '"Chromium";v="120", "Google Chrome";v="120", "Not_A Brand";v="8"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

        for browser in impersonations:
            try:
                logger.info(f"[Level 1] Trying {browser} impersonation for: {url}")

                response = cffi_requests.get(
                    url,
                    headers=api_headers,
                    impersonate=browser,
                    timeout=30,
                )

                if response.status_code == 200 and not self._is_blocked(response.text):
                    logger.info(f"[Level 1] SUCCESS with {browser}")
                    return {
                        "success": True,
                        "method": f"curl_cffi ({browser})",
                        "status_code": response.status_code,
                        "content": response.text,
                    }
                else:
                    logger.debug(f"[Level 1] {browser} blocked - Status: {response.status_code}")

            except Exception as e:
                logger.debug(f"[Level 1] {browser} error: {e}")
                continue

        logger.warning("[Level 1] All browser impersonations failed")
        return None

    def get_with_playwright(self, url: str, headless: bool = True) -> dict[str, Any] | None:
        """
        Level 2: Use Playwright with real browser to handle captcha.
        This can click the Sucuri recaptcha button if needed.
        """
        if not HAS_PLAYWRIGHT:
            logger.error("playwright not available")
            return None

        try:
            logger.info(f"[Level 2] Attempting Playwright request to: {url}")

            with sync_playwright() as p:
                # Launch Chromium browser
                browser = p.chromium.launch(headless=headless)

                # Create context with realistic user agent
                context = browser.new_context(
                    user_agent=self.HEADERS["User-Agent"],
                    viewport={"width": 1920, "height": 1080},
                    locale="pt-BR",
                )

                page = context.new_page()

                # Navigate to page
                page.goto(url, wait_until="domcontentloaded")

                # Check if blocked by Sucuri
                if self._is_blocked(page.content()):
                    logger.info("[Level 2] Sucuri block detected, attempting bypass...")

                    try:
                        # Wait for recaptcha button and click it
                        button = page.wait_for_selector(
                            "button.g-recaptcha", timeout=5000
                        )
                        if button:
                            logger.info("[Level 2] Found recaptcha button, clicking...")
                            button.click()

                            # Wait for navigation after captcha
                            page.wait_for_load_state("networkidle", timeout=15000)
                            logger.info("[Level 2] Captcha clicked, waiting for redirect...")

                    except Exception as e:
                        logger.warning(f"[Level 2] Could not click captcha: {e}")

                # Get final content
                content = page.content()
                browser.close()

                if not self._is_blocked(content):
                    logger.info("[Level 2] SUCCESS - Got content with Playwright")
                    return {
                        "success": True,
                        "method": "playwright",
                        "content": content,
                    }
                else:
                    logger.warning("[Level 2] Still blocked after captcha attempt")
                    return None

        except Exception as e:
            logger.error(f"[Level 2] ERROR: {e}")
            return None

    def get(self, url: str) -> dict[str, Any] | None:
        """
        Try to fetch URL using available bypass methods.
        Returns dict with 'success', 'method', and 'content' keys.
        """
        # Level 1: Try curl_cffi first (faster, no browser overhead)
        if HAS_CURL_CFFI:
            result = self.get_with_curl_cffi(url)
            if result:
                return result

        # Level 2: Fall back to Playwright (slower, but can handle captcha)
        if HAS_PLAYWRIGHT:
            result = self.get_with_playwright(url)
            if result:
                return result

        logger.error("All bypass methods failed")
        return None


# Convenience function
def get_with_bypass(url: str) -> dict[str, Any] | None:
    """Fetch URL with Sucuri bypass. Returns dict with 'content' or None."""
    bypass = SucuriBypass()
    return bypass.get(url)


if __name__ == "__main__":
    # Test the bypass
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    test_url = "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category?url=/proteina/&offset=0&limit=5"

    print("\n=== Testing Sucuri Bypass ===\n")
    print(f"Available methods:")
    print(f"  - curl_cffi: {'✓' if HAS_CURL_CFFI else '✗'}")
    print(f"  - playwright: {'✓' if HAS_PLAYWRIGHT else '✗'}")
    print()

    result = get_with_bypass(test_url)

    if result:
        print(f"\n✓ Success via {result['method']}")
        print(f"Content preview: {result['content'][:200]}...")
    else:
        print("\n✗ All methods failed")
