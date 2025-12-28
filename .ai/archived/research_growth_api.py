import json
import logging

import requests
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_URL = "https://www.gsuplementos.com.br/proteinas"
API_LISTING_URL = (
    "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category"
)


def run():
    with sync_playwright() as p:
        # Launch browser to intercept headers
        cdp_url = "http://localhost:9222"
        print(f"Connecting to {cdp_url}...")
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.new_page()

        headers_captured = {}

        def handle_request(request):
            nonlocal headers_captured
            # Log all API-like requests
            if "api" in request.url or "front" in request.url:
                h = request.headers
                # user said "app-token" or "wapstore"
                token = (
                    h.get("app-token")
                    or h.get("x-auth-token")
                    or h.get("authorization")
                )

                if token:
                    print(f"CAPTURED POSSIBLE TOKEN in {request.url}: {token[:20]}...")
                    headers_captured = h
                elif "listing" in request.url:
                    print(f"Found listing URL but no obvious token: {request.url}")
                    print(f"Headers: {h.keys()}")

        page.on("request", handle_request)

        logger.info(f"Navigating to {TARGET_URL} to capture headers...")
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)  # Wait for JS to fire requests

            # Scroll down to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000)

            if headers_captured:
                print("\n=== HEADERS CAPTURED ===")
                # Clean headers for requests
                clean_headers = {
                    "app-token": headers_captured.get("app-token"),
                    "user-agent": headers_captured.get("user-agent"),
                    "origin": "https://www.gsuplementos.com.br",
                    "referer": "https://www.gsuplementos.com.br/",
                }
                print(clean_headers)

                # Test the listing API
                print(f"\n=== TESTING API: {API_LISTING_URL} ===")
                variations = [
                    "/whey-protein/",
                    "/whey-protein",
                    "whey-protein",
                    "/suplementos/",
                    "/lancamentos/",
                ]

                # Transfer cookies
                print("\n=== TRANSFERRING COOKIES ===")
                cookies = context.cookies()
                session = requests.Session()
                for c in cookies:
                    session.cookies.set(c["name"], c["value"], domain=c["domain"])

                # Retry Listing with Session
                print("\n=== RETRYING LISTING WITH COOKIES ===")
                for v in ["/whey-protein/"]:
                    params = {"url": v, "offset": 0, "limit": 10}  # Ints this time
                    try:
                        resp = requests.get(
                            API_LISTING_URL, headers=clean_headers, params=params
                        )  # type: ignore
                        if resp.status_code == 200:
                            data = resp.json()
                            products = data.get("data", {}).get("list", [])
                            print(f"  -> Found: {len(products)}")
                            if products:
                                print(json.dumps(products[0], indent=2))
                                break
                        else:
                            print(f"  -> Status {resp.status_code}")
                    except Exception as e:
                        print(e)

                # Test Verify URL
                print("\n=== TESTING VERIFY: .../url/verify ===")
                verify_url = "https://www.gsuplementos.com.br/api/v2/front/url/verify"
                try:
                    resp = requests.get(
                        verify_url,
                        headers=clean_headers,
                        params={"url": "/whey-protein/"},
                    )
                    print(f"Verify Status: {resp.status_code}")
                    print(resp.text[:500])
                except Exception as e:
                    print(e)

                # Test Search URL (Guessing)
                print("\n=== TESTING SEARCH: .../search ===")
                search_url = "https://www.gsuplementos.com.br/api/v2/front/showcase/search/search"  # Common pattern?
                # or maybe listing with search param

                # Let's try to verify the listing logic again but with more headers maybe?
                # Or maybe the offset/limit needs to be int? (Requests handles params as strings usually but lets try)

        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run()
