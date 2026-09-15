"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

import json
from http import HTTPStatus

from django.test import TestCase, override_settings


class PublicEndpointSecurityTests(TestCase):
    """Tests for public endpoint access rules."""

    def test_public_catalog_rest_query_without_api_key(self) -> None:
        """Public REST catalog requests should be allowed without API key."""
        response = self.client.get("/api/catalog/products/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert "public" in response["Cache-Control"]
        assert "s-maxage=21600" in response["Cache-Control"]
        assert payload["pageInfo"]["totalCount"] == 0

    def test_healthz_without_api_key(self) -> None:
        """Healthchecks should not depend on GraphQL authentication."""
        response = self.client.get("/healthz/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert payload == {"status": "ok"}

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz/$"])
    def test_healthz_skips_production_ssl_redirect(self) -> None:
        """Container healthchecks should receive a direct 200 in production."""
        response = self.client.get("/healthz/")
        payload = json.loads(response.content)

        assert response.status_code == HTTPStatus.OK
        assert payload == {"status": "ok"}
