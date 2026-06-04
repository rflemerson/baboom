"""Project-specific Django settings for installed apps and templates."""

from baboom.settings.base import INSTALLED_APPS
from baboom.settings.env import BASE_DIR

# Project apps
INSTALLED_APPS += ["common", "offers", "core", "scrapers"]

# Treebeard
INSTALLED_APPS += ["treebeard"]

# Nested Admin
INSTALLED_APPS += ["nested_admin"]

# Strawberry GraphQL
INSTALLED_APPS += ["strawberry.django"]

# Django Components
INSTALLED_APPS += ["django_components"]

# UI Web Components
INSTALLED_APPS += ["web"]

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
        "DIRS": [
            BASE_DIR / "templates",
            BASE_DIR / "web/admin_ui/templates",
        ],
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
                "django_components.template_loader.Loader",
            ],
            "builtins": [
                "django_components.templatetags.component_tags",
            ],
        },
    },
]

# Static Files Finders for Django Components
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "django_components.finders.ComponentsFileSystemFinder",
]

# Django Components Settings
COMPONENTS = {
    "dirs": [BASE_DIR / "web/admin_ui/components"],
    "app_dirs": [],
}
