import logging
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError

from .models import AlertSubscriber

if TYPE_CHECKING:
    from .models import AlertSubscriber

logger = logging.getLogger(__name__)


def alert_subscriber_create(*, email: str) -> "AlertSubscriber":
    """
    Creates a new alert subscriber.
    """
    if AlertSubscriber.objects.filter(email=email).exists():
        raise ValidationError("This email is already subscribed.", code="unique")

    subscriber = AlertSubscriber.objects.create(email=email)
    logger.info(f"New subscriber created: {email}")

    return subscriber
