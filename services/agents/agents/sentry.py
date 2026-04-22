"""Sentry initialization for the agents service."""

import os

import sentry_sdk


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() == "true"


def _env_float(name: str, *, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def init_sentry() -> None:
    """Initialize Sentry when configured for the current process."""
    dsn = os.getenv("AGENTS_SENTRY_DSN", "")
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("AGENTS_SENTRY_ENVIRONMENT", "production"),
        send_default_pii=_env_bool("AGENTS_SENTRY_SEND_DEFAULT_PII", default=False),
        traces_sample_rate=_env_float("AGENTS_SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    )
