"""Promotions app configuration."""

from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    """Promotions, revisions, scopes, effects, rewards and purchase routes."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "promotions"
