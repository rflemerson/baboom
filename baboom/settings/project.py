from baboom.django.base import BASE_DIR, INSTALLED_APPS, MIDDLEWARE

# Project apps
INSTALLED_APPS += ["core", "scrapers"]

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

# Django Widget Tweaks
INSTALLED_APPS += ["widget_tweaks"]

# Django Components
INSTALLED_APPS += ["django_components"]

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media Files (User uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# i18n: Supported languages
LANGUAGE_CODE = "pt-BR"
LANGUAGES = [
    ("pt-BR", "Português (Brasil)"),
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
                "django_components.template_loader.Loader",
            ],
            "builtins": [
                "django_components.templatetags.component_tags",
            ],
        },
    },
]
