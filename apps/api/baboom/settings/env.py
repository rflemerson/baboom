from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = BASE_DIR / "baboom"


def env_to_enum(enum_cls, value):
    """Convert env string to Enum member."""
    for x in enum_cls:
        if x.value == value:
            return x

    raise ImproperlyConfigured(
        f"Env value {value!r} could not be found in {enum_cls!r}",
    )
