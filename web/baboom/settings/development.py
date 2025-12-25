from .base import BASE_DIR

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-5rk^07(a8qlt8i()9s#zdf83ugep_m24c0=y540^c6p$(!ukj0"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "postgres.nfoylbmemuvbniumofmn",
        "PASSWORD": "Baboom@dev!p4ssw0rd",
        "HOST": "aws-1-sa-east-1.pooler.supabase.com",
        "PORT": "5432",
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
