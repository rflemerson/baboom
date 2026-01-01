from django.apps import AppConfig


class ScrapersConfig(AppConfig):
    name = "scrapers"

    def ready(self):
        import scrapers.signals  # noqa: F401
