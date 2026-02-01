import importlib
import os
import pkgutil
from pathlib import Path

from .base import *

apps_folder = Path(__file__).parent / "apps"

for _finder, name, _ in pkgutil.iter_modules([str(apps_folder)]):
    module = importlib.import_module(f".apps.{name}", package=__package__)
    globals().update({k: v for k, v in vars(module).items() if k.isupper()})

del apps_folder, name, module, pkgutil, importlib, Path

env_name = os.getenv("DJANGO_ENV", "development")

if env_name == "production":
    from .production import *
else:
    from .development import *
