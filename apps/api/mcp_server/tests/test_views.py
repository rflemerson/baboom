"""What the MCP endpoint serves, and to whom.

These run behind a stand-in authenticator: which OAuth server issues the
tokens is configuration, and its own behaviour is covered where it lives.
"""

from __future__ import annotations

import json
from http import HTTPStatus

from django.test import TestCase, override_settings

from mcp_server.tests.helpers import _OperatorTokenMixin

MCP_URL = "/mcp/"
OPERATOR_HEADER = "HTTP_X_TEST_OPERATOR"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2024-11-05"},
}


@override_settings(MCP_AUTHENTICATORS=["mcp_server.tests.helpers.HeaderAuthenticator"])
class BearerMcpEndpointTests(_OperatorTokenMixin, TestCase):
    """Cover the ways in and the ways refused."""

    def _post(self, **headers: str) -> object:
        return self.client.post(
            MCP_URL,
            data=json.dumps(INITIALIZE),
            content_type="application/json",
            **headers,
        )

    def test_an_authenticated_request_reaches_the_endpoint(self) -> None:
        """A verified request runs as the identity it was verified as."""
        response = self._post(**self._credentials)

        assert response.status_code == HTTPStatus.OK
        body = json.loads(response.content)
        assert body["result"]["serverInfo"]["name"]

    def test_an_unverified_request_is_refused_with_a_challenge(self) -> None:
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

    def test_manifest_lists_the_tools_behind_the_same_gate(self) -> None:
        """The catalogue is readable by hand, with the same token."""
        response = self.client.get("/mcp/manifest/", **self._credentials)

        assert response.status_code == HTTPStatus.OK
        names = [tool["name"] for tool in json.loads(response.content)["tools"]]
        assert "admin.registry" in names

    def test_manifest_without_authentication_is_refused(self) -> None:
        """The catalogue is not a public description of the server."""
        response = self.client.get("/mcp/manifest/")

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_operator_can_execute_registry_and_product_list(self) -> None:
        """Discovery is not enough: both read tools must finish end to end."""
        for name, arguments in (
            ("admin.registry", {}),
            (
                "admin.list",
                {"app_label": "core", "model_name": "product", "page_size": 1},
            ),
        ):
            response = self.client.post(
                MCP_URL,
                data=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    },
                ),
                content_type="application/json",
                **self._credentials,
            )
            body = json.loads(response.content)
            assert response.status_code == HTTPStatus.OK, (name, body)
            assert "error" not in body, (name, body)
            assert body["result"]["isError"] is False, (name, body)
