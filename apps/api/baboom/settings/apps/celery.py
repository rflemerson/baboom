"""Celery-related Django settings."""

from baboom.settings.base import INSTALLED_APPS
from baboom.settings.env import env

# Celery Configuration
INSTALLED_APPS += ["django_celery_results", "django_celery_beat"]

CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    default="redis://localhost:6379/0",
)
CELERY_RESULT_BACKEND = "django-db"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
