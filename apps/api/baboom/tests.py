"""The OAuth server this deployment runs, and how it is configured."""

from __future__ import annotations

import json
from http import HTTPStatus
from urllib.parse import urlparse

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model

class SigningKeyTests(TestCase):
    """The configured key has to be usable, not merely present."""

    def test_jwks_publishes_a_signing_key(self) -> None:
        """An escaped PEM in the environment still has to parse.

        A PEM kept on one line needs its newlines restored before use, and
        nothing but this endpoint exercises the key.
        """
        response = self.client.get("/o/.well-known/jwks.json")

        assert response.status_code == HTTPStatus.OK
        keys = json.loads(response.content)["keys"]
        assert [key["kty"] for key in keys] == ["RSA"]
        assert keys[0]["alg"] == "RS256"

@override_settings(MCP_CLIENT_HOSTS=["chatgpt.com"])
class DynamicRegistrationTests(TestCase):
    """A connector registers itself; a stranger does not."""

    URL = "/o/register/"
    ALLOWED_REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"

    def _register(self, *redirect_uris: str) -> int:
        response = self.client.post(
            self.URL,
            data=json.dumps(
                {
                    "client_name": "connector",
                    "redirect_uris": list(redirect_uris),
                    "grant_types": ["authorization_code"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                },
            ),
            content_type="application/json",
        )
        return response.status_code

    def test_allowlisted_redirect_registers(self) -> None:
        """The connector has nobody signed in and still must get through."""
        assert self._register(self.ALLOWED_REDIRECT) == HTTPStatus.CREATED

    def test_other_host_is_refused(self) -> None:
        """A code must not be deliverable to a host we did not name."""
        assert self._register("https://evil.example/callback") != HTTPStatus.CREATED

    def test_one_bad_redirect_spoils_the_registration(self) -> None:
        """Every address is checked, not just the first."""
        status = self._register(self.ALLOWED_REDIRECT, "https://evil.example/cb")

        assert status != HTTPStatus.CREATED

    def test_plain_http_is_refused(self) -> None:
        """An authorization code may not travel in clear text."""
        assert self._register("http://chatgpt.com/cb") != HTTPStatus.CREATED

    @override_settings(MCP_CLIENT_HOSTS=[])
    def test_empty_allowlist_denies(self) -> None:
        """Naming no host denies every client, rather than allowing all."""
        assert self._register(self.ALLOWED_REDIRECT) != HTTPStatus.CREATED

class AuthorizationLoginTests(TestCase):
    """Approving an authorization has to reach a page this project serves."""

    def test_signing_in_lands_on_a_served_route(self) -> None:
        """The default login URL is not routed here, so it reaches the site."""
        response = self.client.get(
            "/o/authorize/",
            {
                "response_type": "code",
                "client_id": "whatever",
                "redirect_uri": "https://chatgpt.com/cb",
                "scope": settings.MCP_SCOPE,
            },
        )

        assert response.status_code == HTTPStatus.FOUND
        destination = urlparse(response["Location"]).path
        assert destination == settings.LOGIN_URL
        assert resolve(destination)


class TokenAuthenticatorTests(TestCase):
    """What the deployment's own authenticator accepts on the MCP route."""

    URL = "/mcp/"
    INITIALIZE = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    }

    def setUp(self) -> None:
        """An operator and a client to mint tokens against."""
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
