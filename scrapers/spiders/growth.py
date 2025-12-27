import logging

import requests

from .base_spider import BaseSpider

logger = logging.getLogger(__name__)


class GrowthSpider(BaseSpider):
    BASE_URL = "https://www.gsuplementos.com.br/"

    def fetch_home(self):
        logger.info(f"Fetching {self.BASE_URL}...")
        try:
            response = requests.get(
                self.BASE_URL, headers=self.get_headers(), timeout=10
            )
            response.raise_for_status()
            logger.info(f"Success! Status Code: {response.status_code}")
            return True
        except requests.RequestException as e:
            logger.error(f"Error fetching home: {e}")
            return False
