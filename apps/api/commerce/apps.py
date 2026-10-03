"""Commerce app configuration."""

from django.apps import AppConfig


class CommerceConfig(AppConfig):
    """Channels, markets, sellers, payment methods and programmes."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "commerce"
