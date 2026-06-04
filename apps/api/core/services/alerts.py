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
        normalized_email = email.strip().lower()
        if AlertSubscriber.objects.filter(email=normalized_email).exists():
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
