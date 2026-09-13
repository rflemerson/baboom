"""The MCP route is reachable by access token and by nothing else."""

from __future__ import annotations

import json
from datetime import timedelta
from http import HTTPStatus
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model

MCP_URL = "/mcp/"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2024-11-05"},
}


class _OperatorTokenMixin:
    """An operator, a registered client, and tokens issued for them."""

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


class BearerMcpEndpointTests(_OperatorTokenMixin, TestCase):
    """Cover the ways in and the ways refused."""

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
            "/mcp/manifest/", headers={"authorization": f"Bearer {self._token()}"}
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


class SkillOverMcpTests(_OperatorTokenMixin, TestCase):
    """The curation skill travels with the tools, for whatever a client speaks."""

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        response = self.client.post(
            MCP_URL,
            data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
            ),
            content_type="application/json",
            headers={"authorization": f"Bearer {self._token()}"},
        )
        return json.loads(response.content)

    def test_initialize_advertises_what_it_serves(self) -> None:
        """A client learns from the handshake that skills are available."""
        capabilities = self._rpc(
            "initialize",
            {"protocolVersion": "2024-11-05"},
        )["result"]["capabilities"]

        assert "io.modelcontextprotocol/skills" in capabilities["extensions"]
        assert "prompts" in capabilities
        assert "resources" in capabilities
        assert "tools" in capabilities

    def test_skills_list_names_the_curation_skill(self) -> None:
        """The listing carries the frontmatter a client indexes on."""
        skills = self._rpc("skills/list")["result"]["skills"]

        assert [skill["name"] for skill in skills] == ["product-curation"]
        assert skills[0]["frontmatter"]["description"]
        assert skills[0]["uri"].endswith("/SKILL.md")

    def test_resources_read_returns_a_referenced_file(self) -> None:
        """A reference named by the skill can be fetched by its URI."""
        body = self._rpc(
            "resources/read",
            {"uri": "skill://product-curation/references/catalog-rules.md"},
        )

        text = body["result"]["contents"][0]["text"]
        assert "One product, many offers" in text

    def test_prompt_carries_the_references_inline(self) -> None:
        """A prompt cannot follow a URI, so the references travel with it."""
        body = self._rpc("prompts/get", {"name": "product-curation"})

        text = body["result"]["messages"][0]["content"]["text"]
        assert "price per gram" in text
        assert "One product, many offers" in text

    def test_reading_outside_the_skill_is_refused(self) -> None:
        """A URI may not walk out of the skill directory."""
        body = self._rpc(
            "resources/read",
            {"uri": "skill://product-curation/../../settings/base.py"},
        )

        assert "error" in body

    def test_skill_methods_still_require_a_token(self) -> None:
        """The instructions are behind the same gate as the tools."""
        response = self.client.post(
            MCP_URL,
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "skills/list"}),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED


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
