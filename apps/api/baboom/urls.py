"""Admin, OAuth, MCP, public catalog API, and liveness routes."""

from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import include, path
from oauth2_provider.urls import metadata_urlpatterns


def healthz(_request: HttpRequest) -> JsonResponse:
    """Return a lightweight liveness response for container healthchecks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    # RFC 8414 and RFC 9728 put both metadata documents at the origin root, so
    # a client that only knows the hostname can still find the issuer.
    path(
        "",
        include((metadata_urlpatterns, "oauth2_provider"), namespace="oauth2_metadata"),
    ),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("healthz/", healthz),
    path("admin/", admin.site.urls),
    path("admin-api/", include("django_admin_rest_api.urls")),
    path("mcp/", include("mcp_server.urls")),
    path("api/", include("core.rest.urls")),
]
