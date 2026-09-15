"""Base Django settings shared by development and production."""

from baboom.settings.env import BASE_DIR, env

env.read_env(BASE_DIR / ".env")


SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env.bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS: list[str] = []


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "baboom.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "baboom.wsgi.application"

TEST_RUNNER = "baboom.test_runner.NoNetworkTestRunner"


DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3"),
}

CATALOG_DEFAULT_ACTIVE_SLUG = env.str("CATALOG_DEFAULT_ACTIVE_SLUG", "protein")

CATALOG_PRODUCTS_BROWSER_CACHE_SECONDS = env.int(
    "CATALOG_PRODUCTS_BROWSER_CACHE_SECONDS",
    default=300,
)
CATALOG_PRODUCTS_EDGE_CACHE_SECONDS = env.int(
    "CATALOG_PRODUCTS_EDGE_CACHE_SECONDS",
    default=21600,
)


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
