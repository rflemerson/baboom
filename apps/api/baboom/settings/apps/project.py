from baboom.settings.base import INSTALLED_APPS, MIDDLEWARE
from baboom.settings.env import BASE_DIR

# Project apps
INSTALLED_APPS += ["core", "scrapers"]

# Simple History
INSTALLED_APPS += ["simple_history"]
MIDDLEWARE += ["simple_history.middleware.HistoryRequestMiddleware"]

# Treebeard
INSTALLED_APPS += ["treebeard"]

# Nested Admin
INSTALLED_APPS += ["nested_admin"]

# Django Filter
INSTALLED_APPS += ["django_filters"]

# Strawberry GraphQL
INSTALLED_APPS += ["strawberry.django"]

# Media Files (User uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# i18n: Supported languages
LANGUAGE_CODE = "pt-br"
LANGUAGES = [
    ("pt-br", "Portuguese (Brazil)"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# Templates Configuration
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        },
    },
]
