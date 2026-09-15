"""The OAuth server this deployment runs, and how it is configured."""

from __future__ import annotations

import importlib
import json
import os
from http import HTTPStatus
from unittest.mock import patch
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import resolve

from baboom.settings.apps import oauth as oauth_settings


def _single_line_pem() -> str:
    """Generate an RSA key written the way a CI variable holds it: one line."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return pem.replace("\n", "\\n")


class SigningKeyTests(TestCase):
    """The configured key has to be usable, not merely present."""

    def test_jwks_publishes_a_signing_key(self) -> None:
        """An escaped PEM in the environment still has to parse.

        A PEM kept on one line needs its newlines restored before use, and
        nothing but this endpoint exercises the key. The key is generated here,
        so the test does not depend on a secret present on one machine.
        """
        with patch.dict(os.environ, {"OIDC_RSA_PRIVATE_KEY": _single_line_pem()}):
            provider = importlib.reload(oauth_settings).OAUTH2_PROVIDER
        importlib.reload(oauth_settings)

        with override_settings(OAUTH2_PROVIDER=provider):
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
