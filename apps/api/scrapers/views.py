"""The crawler's public key directory (Web Bot Auth)."""

from __future__ import annotations

import time

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from .crawler.web_bot_auth import DIRECTORY_CONTENT_TYPE, directory, load_private_key


@require_GET
def signature_directory(request: HttpRequest) -> HttpResponse:
    """Publish the crawler's public key, signed for this host."""
    seed = settings.WEB_BOT_AUTH_PRIVATE_KEY
    if not seed:
        raise Http404
    body, headers = directory(
        load_private_key(seed), request.get_host(), int(time.time())
    )
    response = HttpResponse(body, content_type=DIRECTORY_CONTENT_TYPE)
    for name, value in headers.items():
        response[name] = value
    response["Cache-Control"] = "public, max-age=60"
    return response
