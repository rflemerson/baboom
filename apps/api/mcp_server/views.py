"""Bearer-authenticated MCP endpoint.

Which OAuth server issues the tokens is configuration; see ``mcp_server.auth``
for the contract an authenticator honours.
"""

from __future__ import annotations

from django.views.decorators.csrf import csrf_exempt
from django_admin_mcp_api.server.views import ManifestView, McpEndpointView

from mcp_server.auth import AuthenticatedEndpointMixin
from mcp_server.rpc import SkillMethodsMixin


class McpEndpoint(AuthenticatedEndpointMixin, SkillMethodsMixin, McpEndpointView):
    """MCP over JSON-RPC, for an authenticated caller."""


class McpManifest(AuthenticatedEndpointMixin, ManifestView):
    """The tool catalogue as a plain document, for reading by hand."""


# CSRF guards cookie-borne authority; these routes have none to guard.
bearer_mcp_endpoint = csrf_exempt(McpEndpoint.as_view())
bearer_mcp_manifest = csrf_exempt(McpManifest.as_view())
