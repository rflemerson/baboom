"""Tests for AgentClient network and payload behavior."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from agents.client import AgentClient


class TestAgentClient(TestCase):
    """Unit tests for GraphQL HTTP client."""

    @patch("agents.client.requests.post")
    def test_send_returns_json_data_on_success(self, mock_post):
        """Returns decoded JSON when GraphQL request succeeds."""
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": {"ping": "ok"}}
        mock_post.return_value = response

        client = AgentClient()
        result = client._send("query { ping }")

        self.assertEqual(result, {"data": {"ping": "ok"}})
        mock_post.assert_called_once()

    @patch("agents.client.requests.post")
    def test_send_raises_on_graphql_errors(self, mock_post):
        """Raises exception when GraphQL returns errors block."""
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"errors": [{"message": "boom"}]}
        mock_post.return_value = response

        client = AgentClient()
        with self.assertRaisesRegex(Exception, "API Error: boom"):
            client._send("query { fail }")

    @patch("agents.client.requests.post")
    def test_checkout_work_uses_expected_variables(self, mock_post):
        """Sends checkout variables and returns parsed queue item."""
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": {"checkoutScrapedItem": {"id": 7}}}
        mock_post.return_value = response

        client = AgentClient()
        result = client.checkout_work(force=True, target_item_id=99)

        self.assertEqual(result, {"id": 7})
        kwargs = mock_post.call_args.kwargs
        self.assertTrue(kwargs["json"]["variables"]["force"])
        self.assertEqual(kwargs["json"]["variables"]["targetItemId"], 99)

    def test_create_product_raises_on_empty_response(self):
        """Raises when createProduct payload is missing in API response."""
        client = AgentClient()
        with (
            patch.object(client, "_send", return_value={"data": {}}),
            self.assertRaisesRegex(Exception, "empty createProduct response"),
        ):
            client.create_product({"name": "x"})

    def test_create_product_raises_on_missing_product_id(self):
        """Raises when API response has no created product id."""
        client = AgentClient()
        with (
            patch.object(
                client,
                "_send",
                return_value={"data": {"createProduct": {"errors": []}}},
            ),
            self.assertRaisesRegex(Exception, "missing product id"),
        ):
            client.create_product({"name": "x"})
