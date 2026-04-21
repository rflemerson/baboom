"""Sentry error tracking settings."""

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from baboom.settings.env import env

SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = env("DJANGO_ENV", default="development")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)
SENTRY_SEND_DEFAULT_PII = env.bool("SENTRY_SEND_DEFAULT_PII", default=False)
SENTRY_MONITOR_CELERY_BEAT = env.bool("SENTRY_MONITOR_CELERY_BEAT", default=False)

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        send_default_pii=SENTRY_SEND_DEFAULT_PII,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(monitor_beat_tasks=SENTRY_MONITOR_CELERY_BEAT),
        ],
    )
