"""Alert subscription services."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.models import AlertSubscriber

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AlertSubscriptionResult:
    """Outcome of an alert subscription attempt."""

    email: str
    subscriber: AlertSubscriber | None
    already_subscribed: bool


class AlertSubscriptionService:
    """Validate and subscribe emails to price alerts."""

    def execute(self, *, email: str) -> AlertSubscriptionResult:
        """Normalize, validate, and create an alert subscription."""
        normalized_email = self._normalize_email(email)
        if self._is_already_subscribed(normalized_email):
            return AlertSubscriptionResult(
                email=normalized_email,
                subscriber=None,
                already_subscribed=True,
            )

        subscriber = AlertSubscriber(email=normalized_email)
        subscriber.full_clean()
        subscriber.save()

        logger.info("New subscriber created: %s", normalized_email)
        return AlertSubscriptionResult(
            email=normalized_email,
            subscriber=subscriber,
            already_subscribed=False,
        )

    def _normalize_email(self, email: str) -> str:
        """Normalize incoming email values before validation."""
        return email.strip().lower()

    def _is_already_subscribed(self, email: str) -> bool:
        """Return whether a subscription already exists for the email."""
        return AlertSubscriber.objects.filter(email=email).exists()
