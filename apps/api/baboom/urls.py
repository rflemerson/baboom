"""Admin, public catalog API, and liveness routes."""

from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import include, path


def healthz(_request: HttpRequest) -> JsonResponse:
    """Return a lightweight liveness response for container healthchecks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz/", healthz),
    path("admin/", admin.site.urls),
    path("admin-api/", include("django_admin_rest_api.urls")),
    path("api/", include("core.rest.urls")),
]
