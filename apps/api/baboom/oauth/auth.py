"""The authenticator for the OAuth server this deployment runs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.urls import reverse
from oauth2_provider.oauth2_backends import get_oauthlib_core
from oauth2_provider.www_authenticate import build_bearer_challenge

from mcp_server.auth import AuthenticationError

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser
    from django.http import HttpRequest

BEARER = "Bearer "


class TokenAuthenticator:
    """Verify an access token issued by django-oauth-toolkit."""

    realm = "baboom-mcp"

    def authenticate(
        self,
        request: HttpRequest,
    ) -> tuple[AbstractBaseUser, object] | None:
        """Resolve the token's owner, or decline when there is no token."""
        header = request.headers.get("authorization", "")
        if not header.startswith(BEARER):
            return None

        valid, verified = get_oauthlib_core().verify_request(
            request,
            scopes=[settings.MCP_SCOPE],
        )
        if not valid:
            request.oauth2_error = getattr(verified, "oauth2_error", {})
            raise AuthenticationError
        return verified.user, verified.access_token

    def authenticate_header(self, request: HttpRequest) -> str:
        """Name the scheme and where its rules are published."""
        return build_bearer_challenge(
            request,
            oauth2_error=getattr(request, "oauth2_error", None),
            realm=self.realm,
            resource_metadata_url=request.build_absolute_uri(
                reverse("oauth2_metadata:oauth-resource-metadata"),
            ),
        )
