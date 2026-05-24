"""Web application configuration module."""

from importlib import import_module

from django.apps import AppConfig


class WebConfig(AppConfig):
    """Configuration class for the web application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "web"

    def ready(self) -> None:
        """Perform initialization tasks when Django starts."""
        import_module("web.admin_ui.components")
