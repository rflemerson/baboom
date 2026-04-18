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
        """Sends checkout input object and returns parsed queue item."""
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": {"checkoutScrapedItem": {"id": 7}}}
        mock_post.return_value = response

        client = AgentClient()
        result = client.checkout_work(force=True, target_item_id=99)

        self.assertEqual(result, {"id": 7})
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(
            kwargs["json"]["variables"],
            {"data": {"force": True, "targetItemId": 99}},
        )

    def test_report_error_uses_input_object_contract(self):
        """Reports errors with the current GraphQL input-object shape."""
        client = AgentClient()

        with patch.object(client, "_send", return_value={"data": {}}) as mock_send:
            client.report_error(7, "boom", is_fatal=True)

        _query, variables = mock_send.call_args.args
        self.assertEqual(
            variables,
            {
                "data": {
                    "itemId": 7,
                    "message": "boom",
                    "isFatal": True,
                },
            },
        )

    def test_submit_extraction_uses_review_staging_mutation(self):
        """Submits the final payload to the scraper review mutation."""
        client = AgentClient()
        payload = {
            "originScrapedItemId": 7,
            "sourcePageId": 9,
            "sourcePageUrl": "https://example.com/p",
            "storeSlug": "demo",
            "imageReport": "IMAGE REPORT",
            "product": {"name": "Whey", "children": []},
        }

        with patch.object(
            client,
            "_send",
            return_value={
                "data": {
                    "submitAgentExtraction": {
                        "extraction": {
                            "id": 11,
                            "scrapedItemId": 7,
                            "sourcePageId": 9,
                        },
                        "errors": None,
                    },
                },
            },
        ) as mock_send:
            result = client.submit_extraction(payload)

        _query, variables = mock_send.call_args.args
        self.assertEqual(variables, {"data": payload})
        self.assertEqual(result["id"], 11)
