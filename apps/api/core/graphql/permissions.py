"""Permission helpers for GraphQL API access."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from strawberry.permission import BasePermission

from core.models import APIKey

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


class _GraphQLRequest(Protocol):
    """Protocol for GraphQL request objects used by permissions."""

    headers: Mapping[str, str]


class _GraphQLContext(Protocol):
    """Protocol for GraphQL context objects used by permissions."""

    request: _GraphQLRequest


class _GraphQLInfo(Protocol):
    """Protocol for Strawberry info objects used by permissions."""

    context: _GraphQLContext


class IsAuthenticatedWithAPIKey(BasePermission):
    """Permission class to require valid X-API-KEY header."""

    message = "API Key required"

    def has_permission(
        self,
        _source: object,
        info: _GraphQLInfo,
        **_kwargs: object,
    ) -> bool:
        """Check if request has valid API Key."""
        request = info.context.request
        key = request.headers.get("X-API-KEY")

        if not key:
            return False

        try:
            APIKey.objects.get(key=key, is_active=True)
        except APIKey.DoesNotExist:
            logger.warning("Access attempt with invalid API key: %s...", key[:8])
            return False

        return True
