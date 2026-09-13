"""Bearer-authenticated MCP endpoint.

The published MCP route accepts an OAuth access token and nothing else. A
session cookie must not reach it: the browser sends cookies to any route on
the domain, and this one writes to the catalog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django_admin_mcp_api.server.views import ManifestView, McpEndpointView
from oauth2_provider.views.mixins import (
    ProtectedResourceMetadataMixin,
    ProtectedResourceMixin,
)

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponseBase


class _TokenUserMixin:
    """Run the view as the user the token was issued for."""

    def dispatch(
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> HttpResponseBase:
        """Adopt the verified token's owner before the endpoint reads it."""
        request.user = request.resource_owner
        return super().dispatch(request, *args, **kwargs)


class _BearerOnly(
    ProtectedResourceMetadataMixin,
    ProtectedResourceMixin,
    _TokenUserMixin,
):
    """Accept an access token carrying the MCP scope, and nothing else."""

    www_authenticate_realm = "baboom-mcp"

    def get_resource_metadata_url(self, request: HttpRequest) -> str:
        """Point at the document on the origin, where RFC 9728 puts it."""
        return request.build_absolute_uri(
            reverse("oauth2_metadata:oauth-resource-metadata"),
        )

    def get_scopes(self) -> list[str]:
        """Require the one scope that grants entry to this endpoint."""
        return [settings.MCP_SCOPE]

    def dispatch(
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> HttpResponseBase:
        """Discard any session identity before the token is verified."""
        request.user = AnonymousUser()
        return super().dispatch(request, *args, **kwargs)


class BearerMcpEndpointView(_BearerOnly, McpEndpointView):
    """MCP over JSON-RPC, authenticated by access token."""


class BearerManifestView(_BearerOnly, ManifestView):
    """The tool catalogue as a plain document, for reading by hand."""


# CSRF guards cookie-borne authority; these routes have none to guard.
bearer_mcp_endpoint = csrf_exempt(BearerMcpEndpointView.as_view())
bearer_mcp_manifest = csrf_exempt(BearerManifestView.as_view())
