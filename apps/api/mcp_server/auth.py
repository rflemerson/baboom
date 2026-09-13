"""How a request to this endpoint becomes an identity.

The contract is the one Django REST framework settled on and that
django-oauth-toolkit already implements: a class with ``authenticate`` and
``authenticate_header``. Naming several in ``MCP_AUTHENTICATORS`` lets an
external issuer and a local one answer side by side, which is what makes a
migration something other than a flag day.

Nothing here knows who issues tokens.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser
    from django.http import HttpRequest, HttpResponseBase


class AuthenticationFailed(Exception):
    """The request carried this scheme's credentials and they did not hold."""


@runtime_checkable
class Authenticator(Protocol):
    """What a class in ``MCP_AUTHENTICATORS`` has to offer."""

    def authenticate(
        self,
        request: HttpRequest,
    ) -> tuple[AbstractBaseUser, object] | None:
        """Return the identity and its credential, or ``None`` if not ours.

        Raise :class:`AuthenticationFailed` when the credential is this
        scheme's and is invalid, so a later authenticator cannot paper over
        a rejection.
        """
        ...

    def authenticate_header(self, request: HttpRequest) -> str | None:
        """Return this scheme's ``WWW-Authenticate`` value, if it has one."""
        ...


def _authenticators() -> list[Authenticator]:
    return [import_string(path)() for path in settings.MCP_AUTHENTICATORS]


def _challenge(authenticators: list[Authenticator], request: HttpRequest) -> str:
    offered = [
        header
        for header in (auth.authenticate_header(request) for auth in authenticators)
        if header
    ]
    return ", ".join(offered)


class AuthenticatedEndpointMixin:
    """Serve only requests an authenticator vouches for.

    A session cookie is discarded first: the browser attaches cookies to every
    route on the domain, and this one writes to the catalog.
    """

    def dispatch(
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> HttpResponseBase:
        """Authenticate, or answer with what the caller could have sent."""
        request.user = AnonymousUser()
        authenticators = _authenticators()
        identity = None
        for authenticator in authenticators:
            try:
                identity = authenticator.authenticate(request)
            except AuthenticationFailed:
                identity = None
                break
            if identity is not None:
                break

        if identity is None:
            response = HttpResponse(status=HTTPStatus.UNAUTHORIZED)
            challenge = _challenge(authenticators, request)
            if challenge:
                response["WWW-Authenticate"] = challenge
            return response

        request.user, request.auth = identity
        return super().dispatch(request, *args, **kwargs)
