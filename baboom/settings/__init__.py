import os

from .base import *
from .logs import *

# Project apps
INSTALLED_APPS += ["core"]

# Whitenoise
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

# Simple History
INSTALLED_APPS += ["simple_history"]
MIDDLEWARE += ["simple_history.middleware.HistoryRequestMiddleware"]

# Treebeard
INSTALLED_APPS += ["treebeard"]

# Nested Admin
INSTALLED_APPS += ["nested_admin"]

# Django Filter
INSTALLED_APPS += ["django_filters"]

# HTMX
INSTALLED_APPS += ["django_htmx"]
MIDDLEWARE += ["django_htmx.middleware.HtmxMiddleware"]

# Tailwind CSS
INSTALLED_APPS += ["django_tailwind_cli"]

# Heroicons
INSTALLED_APPS += ["heroicons"]
TEMPLATES[0]["OPTIONS"].setdefault("builtins", []).append(
    "heroicons.templatetags.heroicons"
)

# Django Widget Tweaks
INSTALLED_APPS += ["widget_tweaks"]

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "assets"]

env_name = os.getenv("DJANGO_ENV", "development")

if env_name == "production":
    from .production import *
else:
    from .development import *
