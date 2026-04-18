"""Tests for fixes identified in code review."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests

from agents.brain import _build_multimodal_user_content
from agents.extraction import CONTEXT_BLOCK_CHAR_LIMIT, build_json_context_block


class TestReviewFixes(TestCase):
    """Tests for fixes identified in code review."""

    @patch("agents.brain.requests.get")
    def test_build_multimodal_user_content_handles_query_strings(self, mock_get):
        """Image extension detection should ignore query strings."""
        mock_get.return_value = MagicMock(
            content=b"img-data",
            raise_for_status=MagicMock(),
        )

        # URL with query string that previously would fail (extension becomes "jpg?v=123")
        image_urls = ["https://example.com/image.jpg?v=123"]

        user_content, loaded_count = _build_multimodal_user_content(
            prompt="PROMPT",
            name="NAME",
            description="DESC",
            image_urls=image_urls,
        )

        self.assertEqual(loaded_count, 1)
        # Verify it detected image/jpeg
        self.assertEqual(user_content[1].media_type, "image/jpeg")

    @patch("agents.brain.requests.get")
    def test_build_multimodal_user_content_handles_request_exception(self, mock_get):
        """Transient HTTP failures should be caught and logged as warnings."""
        mock_get.side_effect = requests.RequestException("Connection error")

        image_urls = ["https://example.com/fail.jpg"]

        # Should not raise exception
        user_content, loaded_count = _build_multimodal_user_content(
            prompt="PROMPT",
            name="NAME",
            description="DESC",
            image_urls=image_urls,
        )

        self.assertEqual(loaded_count, 0)
        self.assertEqual(len(user_content), 1)  # Only text prompt

    def test_build_json_context_block_truncation_marker(self):
        """Truncated context blocks should have an explicit marker in the title."""
        large_payload = {"key": "x" * CONTEXT_BLOCK_CHAR_LIMIT}

        block = build_json_context_block("TEST_BLOCK", large_payload)

        self.assertIn("[TEST_BLOCK (TRUNCATED)]", block)
        self.assertIn("[/TEST_BLOCK (TRUNCATED)]", block)
        self.assertIn("...", block)
