import logging
import typing

from strawberry.permission import BasePermission

from core.models import APIKey

logger = logging.getLogger(__name__)


class IsAuthenticatedWithAPIKey(BasePermission):
    """Permission class to require valid X-API-KEY header."""

    message = "API Key required"

    def has_permission(
        self, source: typing.Any, info: typing.Any, **kwargs: typing.Any
    ) -> bool:
        """Check if request has valid API Key."""
        request = info.context.request
        key = request.headers.get("X-API-KEY")

        if not key:
            return False

        try:
            APIKey.objects.get(key=key, is_active=True)
            return True
        except APIKey.DoesNotExist:
            logger.warning("Access attempt with invalid API key: %s...", key[:8])
            return False
