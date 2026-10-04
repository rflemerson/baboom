"""Pricing app configuration."""

from django.apps import AppConfig


class PricingConfig(AppConfig):
    """Quotes, policies, projections and the engine that computes them."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "pricing"
