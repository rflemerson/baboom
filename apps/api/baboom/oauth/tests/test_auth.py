"""The OAuth server this deployment runs, and how it is configured."""

from __future__ import annotations

import json
from datetime import timedelta
from http import HTTPStatus
from typing import ClassVar

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model


class TokenAuthenticatorTests(TestCase):
    """What the deployment's own authenticator accepts on the MCP route."""

    URL = "/mcp/"
    INITIALIZE: ClassVar[dict[str, object]] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    }

    def setUp(self) -> None:
        """Create an operator and a client to mint tokens against."""
        call_command("ensure_catalog_operator", username="catalog-operator")
        self.user = get_user_model().objects.get(username="catalog-operator")
        self.application = get_application_model().objects.create(
            name="test-client",
            user=self.user,
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris="https://chatgpt.com/cb",
        )

    def _token(self, *, scope: str = "", expires_in: int = 300) -> str:
        token = get_access_token_model().objects.create(
            user=self.user,
            application=self.application,
            token=f"token-{scope or 'mcp'}-{expires_in}",
            scope=scope or settings.MCP_SCOPE,
            expires=timezone.now() + timedelta(seconds=expires_in),
        )
        return str(token.token)

    def _post(self, token: str | None) -> object:
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return self.client.post(
            self.URL,
            data=json.dumps(self.INITIALIZE),
            content_type="application/json",
            **headers,
        )

    def test_a_token_with_the_scope_is_accepted(self) -> None:
        """The endpoint runs as the user the token was issued for."""
        response = self._post(self._token())

        assert response.status_code == HTTPStatus.OK

    def test_a_token_without_the_scope_is_refused(self) -> None:
        """A token minted for something else does not open this door."""
        response = self._post(self._token(scope="read"))

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_an_expired_token_is_refused(self) -> None:
        """Expiry is enforced, not merely recorded."""
        response = self._post(self._token(expires_in=-60))

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_a_session_cookie_does_not_authenticate(self) -> None:
        """A browser session must not carry authority onto this route."""
        self.client.force_login(self.user)

        response = self._post(None)

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_the_refusal_points_at_the_resource_metadata(self) -> None:
        """A client learns from the refusal how it could authenticate."""
        response = self._post(None)

        challenge = response.headers["WWW-Authenticate"]
        assert challenge.startswith("Bearer ")
        assert "/.well-known/oauth-protected-resource" in challenge
