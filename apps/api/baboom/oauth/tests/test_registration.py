"""The OAuth server this deployment runs, and how it is configured."""

from __future__ import annotations

import json
from http import HTTPStatus

from django.test import TestCase, override_settings


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
