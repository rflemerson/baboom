"""Environment helpers for Django settings."""

from enum import Enum
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = BASE_DIR / "baboom"


def env_to_enum[EnumType: Enum](enum_cls: type[EnumType], value: str) -> EnumType:
    """Convert env string to Enum member."""
    for x in enum_cls:
        if x.value == value:
            return x

    message = f"Env value {value!r} could not be found in {enum_cls!r}"
    raise ImproperlyConfigured(message)
