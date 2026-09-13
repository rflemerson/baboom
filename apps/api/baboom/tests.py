"""The MCP route is reachable by access token and by nothing else."""

from __future__ import annotations

import json
from datetime import timedelta
from http import HTTPStatus

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model

MCP_URL = "/mcp/"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2024-11-05"},
}


class BearerMcpEndpointTests(TestCase):
    """Cover the ways in and the ways refused."""

    def setUp(self) -> None:
        """Provision the operator and one registered client."""
        call_command("ensure_catalog_operator", username="catalog-operator")
        self.user = get_user_model().objects.get(username="catalog-operator")
        self.application = get_application_model().objects.create(
            name="test-client",
            user=self.user,
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris="https://example.com/callback",
        )

    def _token(self, *, scope: str = "", expires_in: int = 300) -> str:
        token = get_access_token_model().objects.create(
            user=self.user,
            application=self.application,
            token=f"token-{scope or 'none'}-{expires_in}",
            scope=scope or settings.MCP_SCOPE,
            expires=timezone.now() + timedelta(seconds=expires_in),
        )
        return str(token.token)

    def _post(self, **headers: str) -> object:
        return self.client.post(
            MCP_URL,
            data=json.dumps(INITIALIZE),
            content_type="application/json",
            **headers,
        )

    def test_valid_token_reaches_the_endpoint(self) -> None:
        """A token carrying the scope runs as the user it was issued for."""
        response = self._post(HTTP_AUTHORIZATION=f"Bearer {self._token()}")

        assert response.status_code == HTTPStatus.OK
        body = json.loads(response.content)
        assert body["result"]["serverInfo"]["name"]

    def test_missing_token_is_refused_with_a_challenge(self) -> None:
        """The refusal names where the client can learn how to authenticate."""
        response = self._post()

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        challenge = response.headers["WWW-Authenticate"]
        assert challenge.startswith("Bearer ")
        assert 'resource_metadata="http://testserver/.well-known' in challenge

    def test_session_cookie_does_not_authenticate(self) -> None:
        """A browser session must not carry authority onto this route.

        Cookies ride along on every request to the domain, and this one
        writes to the catalog.
        """
        self.client.force_login(self.user)

        response = self._post()

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_token_without_the_scope_is_refused(self) -> None:
        """A token minted for something else does not open this door."""
        response = self._post(
            HTTP_AUTHORIZATION=f"Bearer {self._token(scope='read')}",
        )

        assert response.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}

    def test_manifest_lists_the_tools_behind_the_same_gate(self) -> None:
        """The catalogue is readable by hand, with the same token."""
        response = self.client.get(
            "/mcp/manifest/",
            HTTP_AUTHORIZATION=f"Bearer {self._token()}",
        )

        assert response.status_code == HTTPStatus.OK
        names = [tool["name"] for tool in json.loads(response.content)["tools"]]
        assert "admin.registry" in names

    def test_manifest_without_a_token_is_refused(self) -> None:
        """The catalogue is not a public description of the server."""
        response = self.client.get("/mcp/manifest/")

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_expired_token_is_refused(self) -> None:
        """Expiry is enforced, not merely recorded."""
        response = self._post(
            HTTP_AUTHORIZATION=f"Bearer {self._token(expires_in=-60)}",
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
