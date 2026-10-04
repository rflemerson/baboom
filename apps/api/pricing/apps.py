"""Pricing app configuration."""

from importlib import import_module

from django.apps import AppConfig


class PricingConfig(AppConfig):
    """Quotes, policies, projections and the engine that computes them."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "pricing"

    def ready(self) -> None:
        """Connect the receivers once the models are loaded."""
        import_module("pricing.receivers")
