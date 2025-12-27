from random import uniform
from time import sleep


class BaseSpider:
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36",
    ]

    def get_headers(self):
        return {
            "User-Agent": self.user_agents[0],  # Simple rotation logic for now
            "Accept-Language": "en-US,en;q=0.9",
        }

    def sleep_random(self, min_seconds=1, max_seconds=3):
        sleep(uniform(min_seconds, max_seconds))  # noqa: S311
