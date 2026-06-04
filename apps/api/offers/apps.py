"""Offers app configuration."""

from django.apps import AppConfig


class OffersConfig(AppConfig):
    """Django app configuration for merchant offers."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "offers"
