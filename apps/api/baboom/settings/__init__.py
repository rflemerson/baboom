"""Settings composition entrypoint for the Django project."""

from __future__ import annotations

import importlib
import os
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


def _load_settings_module(module: ModuleType) -> None:
    """Load uppercase settings from a module into the current namespace."""
    globals().update(
        {key: value for key, value in vars(module).items() if key.isupper()},
    )


_load_settings_module(importlib.import_module(".base", package=__package__))

apps_folder = Path(__file__).parent / "apps"

for _finder, name, _ in pkgutil.iter_modules([str(apps_folder)]):
    module = importlib.import_module(f".apps.{name}", package=__package__)
    _load_settings_module(module)

del apps_folder, name, module, pkgutil, Path

env_name = os.getenv("DJANGO_ENV", "development")

if env_name == "production":
    env_module = importlib.import_module(".production", package=__package__)
else:
    env_module = importlib.import_module(".development", package=__package__)

_load_settings_module(env_module)

del env_module, importlib, _load_settings_module
