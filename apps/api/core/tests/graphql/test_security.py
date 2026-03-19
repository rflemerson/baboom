"""GraphQL tests for API key security behavior."""

from __future__ import annotations

import json
from typing import Any, cast

from django.test import RequestFactory, TestCase
from strawberry.django.views import GraphQLView

from baboom.schema import schema
from core.models import APIKey


class GraphQLSecurityTests(TestCase):
    """Tests for GraphQL API security."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.factory = RequestFactory()
        self.api_key_obj = APIKey.objects.create(name="Test Client")
        self.valid_key = self.api_key_obj.key
        self.view = GraphQLView.as_view(schema=schema)

    def _execute_query(
        self,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        """Execute the hello query and decode the JSON response."""
        query = "{ hello }"
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": query}),
            content_type="application/json",
            **headers if headers else {},
        )
        response = self.view(request)
        if hasattr(response, "content"):
            return json.loads(cast("Any", response).content)
        return json.loads(b"{}")

    def test_query_without_api_key(self) -> None:
        """Test that requests without API key are denied."""
        result = self._execute_query()
        assert "errors" in result
        assert result["errors"][0]["message"] == "API Key required"

    def test_query_with_valid_api_key(self) -> None:
        """Test that requests with valid API key are allowed."""
        result = self._execute_query(headers={"HTTP_X_API_KEY": self.valid_key})
        assert "data" in result
        assert result["data"]["hello"] == "Baboom GraphQL API is Online"

    def test_query_with_invalid_api_key(self) -> None:
        """Test that requests with invalid API key are denied."""
        result = self._execute_query(headers={"HTTP_X_API_KEY": "invalid-key"})
        assert "errors" in result
        assert result["errors"][0]["message"] == "API Key required"

    def test_query_with_disabled_api_key(self) -> None:
        """Test that requests with disabled API key are denied."""
        self.api_key_obj.is_active = False
        self.api_key_obj.save()

        result = self._execute_query(headers={"HTTP_X_API_KEY": self.valid_key})
        assert "errors" in result
        assert result["errors"][0]["message"] == "API Key required"
