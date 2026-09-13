"""Django app configuration for scraper workflows."""

from django.apps import AppConfig

from . import checks


class ScrapersConfig(AppConfig):
    """Django AppConfig for scrapers."""

    name = "scrapers"

    def ready(self) -> None:
        """Register scraper system checks once Django has loaded the app."""
        _ = checks
