"""What the MCP endpoint serves, and to whom.

These run behind a stand-in authenticator: which OAuth server issues the
tokens is configuration, and its own behaviour is covered where it lives.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path

import jsonschema
from django.conf import settings
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
class SkillOverMcpTests(_OperatorTokenMixin, TestCase):
    """The curation skill travels with the tools, for whatever a client speaks."""

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        response = self.client.post(
            MCP_URL,
            data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
            ),
            content_type="application/json",
            **self._credentials,
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

    def test_skill_methods_are_behind_the_same_gate(self) -> None:
        """The instructions are no more public than the tools."""
        response = self.client.post(
            MCP_URL,
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "skills/list"}),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED


@override_settings(MCP_AUTHENTICATORS=["mcp_server.tests.helpers.HeaderAuthenticator"])
class ProtocolHandshakeTests(_OperatorTokenMixin, TestCase):
    """Every call a client makes on connecting has to be answered."""

    def _rpc(self, method: str, *, notification: bool = False) -> object:
        payload: dict[str, object] = {"jsonrpc": "2.0", "method": method}
        if not notification:
            payload["id"] = 1
            payload["params"] = {}
        return self.client.post(
            MCP_URL,
            data=json.dumps(payload),
            content_type="application/json",
            **self._credentials,
        )

    def test_a_notification_is_not_answered_with_an_error(self) -> None:
        """A notification carries no id, so an error envelope has nowhere to go.

        A client that sent one and got back a failure reads the server as
        broken and abandons the connection.
        """
        response = self._rpc("notifications/initialized", notification=True)

        assert response.status_code == HTTPStatus.ACCEPTED
        assert not response.content

    def test_every_declared_capability_answers_its_methods(self) -> None:
        """Announcing a capability is a promise to serve all of it.

        ``resources`` was advertised while ``resources/templates/list`` was
        not implemented, so a client following the handshake hit an error.
        """
        for method in (
            "ping",
            "tools/list",
            "resources/list",
            "resources/templates/list",
            "prompts/list",
            "skills/list",
        ):
            response = self._rpc(method)

            assert response.status_code == HTTPStatus.OK, method
            assert "error" not in json.loads(response.content), method


@override_settings(MCP_AUTHENTICATORS=["mcp_server.tests.helpers.HeaderAuthenticator"])
class ProtocolSchemaTests(_OperatorTokenMixin, TestCase):
    """Every response is held against the protocol's own schema.

    The library that supplies the tools validates the arguments it receives
    and never what it returns, so nothing else here would notice a response
    shaped in a way no client can read.
    """

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "spec"
    CASES = (
        ("initialize", {}, "InitializeResult"),
        ("tools/list", {}, "ListToolsResult"),
        ("resources/list", {}, "ListResourcesResult"),
        (
            "resources/read",
            {"uri": "skill://product-curation/SKILL.md"},
            "ReadResourceResult",
        ),
        ("prompts/list", {}, "ListPromptsResult"),
        ("prompts/get", {"name": "product-curation"}, "GetPromptResult"),
        (
            "resources/templates/list",
            {},
            "ListResourceTemplatesResult",
        ),
        ("ping", {}, "EmptyResult"),
        (
            "tools/call",
            {"name": "admin.registry", "arguments": {}},
            "CallToolResult",
        ),
    )

    @classmethod
    def setUpClass(cls) -> None:
        """Load the schema for the version this server announces."""
        super().setUpClass()
        path = cls.SCHEMA_DIR / f"schema-{settings.MCP_PROTOCOL_VERSION}.json"
        assert path.is_file(), f"No vendored schema for {settings.MCP_PROTOCOL_VERSION}"
        cls.schema = json.loads(path.read_text())

    def _result(self, method: str, params: dict) -> dict:
        response = self.client.post(
            MCP_URL,
            data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            ),
            content_type="application/json",
            **self._credentials,
        )
        body = json.loads(response.content)
        assert "result" in body, f"{method}: {body}"
        return body["result"]

    def test_the_announced_version_is_the_one_served(self) -> None:
        """Announcing a version is a claim, so check the server makes it."""
        result = self._result("initialize", {})

        assert result["protocolVersion"] == settings.MCP_PROTOCOL_VERSION

    def test_every_response_matches_the_published_schema(self) -> None:
        """A result no client can read is a result the server should not send."""
        for method, params, result_type in self.CASES:
            validator = jsonschema.Draft202012Validator(
                {
                    "$ref": f"#/definitions/{result_type}",
                    "definitions": self.schema["definitions"],
                },
            )
            errors = list(validator.iter_errors(self._result(method, params)))

            assert not errors, f"{method} does not match {result_type}: " + "; ".join(
                f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
                for e in errors[:3]
            )
