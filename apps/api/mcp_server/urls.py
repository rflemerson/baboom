"""Routes for the MCP endpoint."""

from django.urls import path

from mcp_server.views import bearer_mcp_endpoint, bearer_mcp_manifest

app_name = "mcp_server"

urlpatterns = [
    path("", bearer_mcp_endpoint, name="endpoint"),
    path("manifest/", bearer_mcp_manifest, name="manifest"),
]
