from .base import BASE_DIR, INSTALLED_APPS, MIDDLEWARE

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

# Django Widget Tweaks
INSTALLED_APPS += ["widget_tweaks"]

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Logging Configuration
# Best Practice: Structured/JSON logging recommended for Production.
# Currently set to Console/Simple for Development.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
