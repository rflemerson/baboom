"""Shared helpers for MCP endpoint tests."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command

from mcp_server.auth import AuthenticationError


class HeaderAuthenticator:
    """Stand-in that honours the same contract as the real one.

    The endpoint is written against a list of authenticators, so its own
    tests need no OAuth server -- and needing none is the proof that the
    endpoint does not depend on one.
    """

    def authenticate(self, request: object) -> tuple[object, object] | None:
        """Resolve the user named in the test header."""
        username = request.headers.get("x-test-operator")
        if not username:
            return None
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise AuthenticationError
        return user, None

    def authenticate_header(self, request: object) -> str:
        """Offer the same shape of challenge a real scheme would."""
        metadata = request.build_absolute_uri(
            "/.well-known/oauth-protected-resource",
        )
        return f'Bearer realm="baboom-mcp",resource_metadata="{metadata}"'


class _OperatorTokenMixin:
    """The catalog operator, recognised by the stand-in authenticator."""

    def setUp(self) -> None:
        """Provision the operator these requests run as."""
        call_command("ensure_catalog_operator", username="catalog-operator")
        self.user = get_user_model().objects.get(username="catalog-operator")

    @property
    def _credentials(self) -> dict[str, str]:
        return {"HTTP_X_TEST_OPERATOR": self.user.username}
