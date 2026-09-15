"""The OAuth server this deployment runs, and how it is configured."""

from __future__ import annotations

import json
from http import HTTPStatus
from urllib.parse import urlparse

from django.conf import settings
from django.test import TestCase
from django.urls import resolve


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
