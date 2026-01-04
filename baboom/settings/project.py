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

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# i18n: Supported languages
LANGUAGE_CODE = "pt-BR"
LANGUAGES = [
    ("pt-BR", "Português (Brasil)"),
    ("en", "English"),
    ("es", "Español"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# LocaleMiddleware (after SessionMiddleware, before CommonMiddleware)
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.contrib.sessions.middleware.SessionMiddleware") + 1,
    "django.middleware.locale.LocaleMiddleware",
)
