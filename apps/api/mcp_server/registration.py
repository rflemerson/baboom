"""Who may register a client without being signed in.

A connector arrives with nobody signed in, so the shipped permission class
refuses it. Registration on its own grants nothing -- a token still requires
a curator to log in and approve -- but an open endpoint lets anyone create
rows. This accepts a registration only when every address the authorization
code could be sent to belongs to a host named in settings.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from django.conf import settings
from django.http.request import validate_host

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)


class RedirectHostAllowlistDCRPermission:
    """Allow anonymous registration for allowlisted redirect hosts only."""

    def has_permission(self, request: HttpRequest) -> bool:
        """Accept when every redirect URI is HTTPS on an allowed host."""
        allowed = settings.MCP_CLIENT_HOSTS
        if not allowed:
            return False
        try:
            payload = json.loads(request.body.decode() or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        redirect_uris = payload.get("redirect_uris")
        if not isinstance(redirect_uris, list) or not redirect_uris:
            return False
        for uri in redirect_uris:
            parsed = urlparse(str(uri))
            if parsed.scheme != "https" or not parsed.hostname:
                return False
            if not validate_host(parsed.hostname, allowed):
                logger.warning(
                    "mcp.registration.rejected_host",
                    extra={"host": parsed.hostname},
                )
                return False
        return True
