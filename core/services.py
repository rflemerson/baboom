import logging
from typing import TYPE_CHECKING

from .models import AlertSubscriber

if TYPE_CHECKING:
    from .models import AlertSubscriber

logger = logging.getLogger(__name__)


def alert_subscriber_create(*, email: str) -> AlertSubscriber:
    """
    Creates a new alert subscriber.
    """
    subscriber = AlertSubscriber(email=email)
    subscriber.full_clean()
    subscriber.save()

    logger.info(f"New subscriber created: {email}")

    return subscriber
