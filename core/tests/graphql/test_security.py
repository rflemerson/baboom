import json

from django.test import RequestFactory, TestCase
from strawberry.django.views import GraphQLView

from baboom.schema import schema
from core.models import APIKey


class GraphQLSecurityTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.api_key_obj = APIKey.objects.create(name="Test Client")
        self.valid_key = self.api_key_obj.key
        self.view = GraphQLView.as_view(schema=schema)

    def _execute_query(self, headers=None):
        query = "{ hello }"
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": query}),
            content_type="application/json",
            **headers if headers else {},
        )
        response = self.view(request)
        if hasattr(response, "content"):
            return json.loads(response.content)
        return json.loads(b"{}")

    def test_query_without_api_key(self):
        """Test that requests without API key are denied."""
        result = self._execute_query()
        self.assertIn("errors", result)
        self.assertEqual(result["errors"][0]["message"], "API Key required")

    def test_query_with_valid_api_key(self):
        """Test that requests with valid API key are allowed."""
        result = self._execute_query(headers={"HTTP_X_API_KEY": self.valid_key})
        self.assertIn("data", result)
        self.assertEqual(result["data"]["hello"], "Baboom GraphQL API is Online")

    def test_query_with_invalid_api_key(self):
        """Test that requests with invalid API key are denied."""
        result = self._execute_query(headers={"HTTP_X_API_KEY": "invalid-key"})
        self.assertIn("errors", result)
        self.assertEqual(result["errors"][0]["message"], "API Key required")

    def test_query_with_disabled_api_key(self):
        """Test that requests with disabled API key are denied."""
        self.api_key_obj.is_active = False
        self.api_key_obj.save()

        result = self._execute_query(headers={"HTTP_X_API_KEY": self.valid_key})
        self.assertIn("errors", result)
        self.assertEqual(result["errors"][0]["message"], "API Key required")
