
import json
import logging
import sys
import time

from playwright.sync_api import sync_playwright

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LojaIntegradaClient:
    """
    Documentation and Testing Script for Loja Integrada (Soldiers Nutrition).
    Uses Playwright to render pages and extract LIgtagDataLayer.
    """

    # Default to a product page that we know exists for testing
    DEFAULT_URL = "https://www.soldiersnutrition.com.br/produto/whey-protein-concentrado-100-puro-importado-sabor-baunilha-1kg-soldiers-nutrition"

    def inspect(self, url: str):
        logger.info(f"--- Launching Browser to inspect: {url} ---")

        with sync_playwright() as p:
            # Launch chromium in headless mode
            browser = p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            page = browser.new_page()

            logger.info("Loading page...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                logger.info("Page loaded (domcontentloaded). Waiting 3s for scripts...")
                time.sleep(3)

                # 1. Get Title
                logger.info(f"Page Title: {page.title()}")

                # 2. Extract Prices (Visible in DOM)
                logger.info("\n[1] DOM Prices (Rendered by JS):")

                # Evaluate script to get clean text
                prices = page.evaluate("""() => {
                    const pDe = document.querySelector('.preco-de');
                    const pPor = document.querySelector('.preco-promocional');
                    const pVenda = document.querySelector('.preco-venda');
                    return {
                        'preco-de': pDe ? pDe.innerText : null,
                        'preco-promocional': pPor ? pPor.innerText : null,
                        'preco-venda': pVenda ? pVenda.innerText : null
                    }
                }""")

                for k, v in prices.items():
                    logger.info(f"    {k}: {v}")

                # 3. Extract LIgtagDataLayer (Window Object)
                logger.info("\n[2] window.LIgtagDataLayer (JS Object):")
                data_layer = page.evaluate("() => window.LIgtagDataLayer")

                if data_layer:
                    # Custom serializer for datetime objects if present
                    print(
                        json.dumps(data_layer, indent=2, ensure_ascii=False, default=str)
                    )
                else:
                    logger.warning(
                        "    window.LIgtagDataLayer is null or undefined (Expected on Category Pages)."
                    )

                # 4. Extract dataLayer for comparison
                logger.info("\n[3] window.dataLayer (GA4/GTM):")
                data_layer_gtm = page.evaluate("() => window.dataLayer")
                if data_layer_gtm:
                    logger.info(f"    Found {len(data_layer_gtm)} items in dataLayer.")
                    # find view_item or similar
                    view_item = next(
                        (
                            item
                            for item in data_layer_gtm
                            if isinstance(item, dict)
                            and item.get("event") == "view_item"
                        ),
                        None,
                    )
                    if view_item:
                        logger.info("    Found 'view_item' event in dataLayer:")
                        print(
                            json.dumps(
                                view_item, indent=2, ensure_ascii=False, default=str
                            )
                        )
                else:
                    logger.warning("    window.dataLayer is empty/null.")

            except Exception as e:
                logger.error(f"Error during inspection: {e}")
            finally:
                browser.close()


if __name__ == "__main__":
    client = LojaIntegradaClient()
    target_url = sys.argv[1] if len(sys.argv) > 1 else LojaIntegradaClient.DEFAULT_URL
    client.inspect(target_url)
