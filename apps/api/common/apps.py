"""Common app configuration."""

from django.apps import AppConfig


class CommonConfig(AppConfig):
    """Django app configuration for shared project code."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "common"
