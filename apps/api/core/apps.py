"""App configuration for the core Django app."""

from importlib import import_module

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Django AppConfig for core."""

    name = "core"

    def ready(self) -> None:
        """Connect the receivers that keep derived catalog data current."""
        import_module(f"{self.name}.signals")
