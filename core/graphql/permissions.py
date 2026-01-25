import typing

from strawberry.permission import BasePermission

from core.models import APIKey


class IsAuthenticatedWithAPIKey(BasePermission):
    message = "API Key required"

    def has_permission(
        self, source: typing.Any, info: typing.Any, **kwargs: typing.Any
    ) -> bool:
        request = info.context.request
        key = request.headers.get("X-API-KEY")

        if not key:
            return False

        try:
            APIKey.objects.get(key=key, is_active=True)
            return True
        except APIKey.DoesNotExist:
            return False
