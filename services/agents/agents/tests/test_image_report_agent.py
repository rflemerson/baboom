"""Tests for image-report agent behavior."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests

from agents.brain import run_image_report_extraction


class TestImageReportAgent(TestCase):
    """Tests for multimodal image-report helper."""

    @patch("agents.brain.requests.get")
    @patch("agents.brain.Agent")
    def test_run_image_report_extraction_uses_supported_images(
        self,
        mock_agent_cls,
        mock_get,
    ):
        """Sends prompt text plus only supported image formats to agent."""
        agent = MagicMock()
        agent.run_sync.return_value = type("R", (), {"output": "RAW"})()
        mock_agent_cls.return_value = agent
        mock_get.side_effect = [
            MagicMock(content=b"img-a", raise_for_status=MagicMock()),
            MagicMock(content=b"img-b", raise_for_status=MagicMock()),
        ]

        result = run_image_report_extraction(
            run_label="Product",
            description="Description",
            image_urls=[
                "https://cdn.example.com/a.jpg",
                "https://cdn.example.com/b.gif",
            ],
            prompt="PROMPT",
            model_name="google-gla:gemini",
        )

        self.assertEqual(result, "RAW")
        self.assertEqual(mock_agent_cls.call_args.args[0], "google-gla:gemini")
        call_args = agent.run_sync.call_args.args[0]
        self.assertEqual(len(call_args), 2)  # text + one supported image
        self.assertNotIn("Product Name:", call_args[0])

    @patch("agents.brain.requests.get")
    @patch("agents.brain.Agent")
    def test_run_image_report_extraction_supports_querystring_image_urls(
        self,
        mock_agent_cls,
        mock_get,
    ):
        """Resolves media type from the URL path, not the querystring."""
        agent = MagicMock()
        agent.run_sync.return_value = type("R", (), {"output": "RAW"})()
        mock_agent_cls.return_value = agent
        mock_get.return_value = MagicMock(content=b"img", raise_for_status=MagicMock())

        run_image_report_extraction(
            run_label="Product",
            description="Description",
            image_urls=["https://cdn.example.com/a.jpg?v=1"],
            prompt="PROMPT",
            model_name="google-gla:gemini",
        )

        call_args = agent.run_sync.call_args.args[0]
        self.assertEqual(len(call_args), 2)

    @patch("agents.brain.requests.get")
    @patch("agents.brain.Agent")
    def test_run_image_report_extraction_skips_failed_image_downloads(
        self,
        mock_agent_cls,
        mock_get,
    ):
        """Skips individual image download failures instead of failing the step."""
        agent = MagicMock()
        agent.run_sync.return_value = type("R", (), {"output": "RAW"})()
        mock_agent_cls.return_value = agent
        mock_get.side_effect = requests.RequestException("cdn down")

        result = run_image_report_extraction(
            run_label="Product",
            description="Description",
            image_urls=["https://cdn.example.com/a.jpg"],
            prompt="PROMPT",
            model_name="google-gla:gemini",
        )

        self.assertEqual(result, "RAW")
        call_args = agent.run_sync.call_args.args[0]
        self.assertEqual(len(call_args), 1)

    @patch("agents.brain.Agent")
    def test_run_image_report_extraction_returns_output(self, mock_agent_cls):
        """Returns the Agent output string."""
        agent = MagicMock()
        agent.run_sync.return_value = type("R", (), {"output": "RAW-OUT"})()
        mock_agent_cls.return_value = agent

        result = run_image_report_extraction(
            run_label="Product",
            description="",
            image_urls=[],
            prompt="PROMPT",
            model_name="openai:gpt-5.2",
        )
        self.assertEqual(result, "RAW-OUT")

    @patch("agents.brain.Agent")
    def test_run_image_report_extraction_raises_on_agent_error(self, mock_agent_cls):
        """Re-raises exceptions from Agent execution."""
        agent = MagicMock()
        agent.run_sync.side_effect = RuntimeError("boom")
        mock_agent_cls.return_value = agent

        with self.assertRaisesRegex(RuntimeError, "boom"):
            run_image_report_extraction(
                run_label="Product",
                description="",
                image_urls=[],
                prompt="PROMPT",
                model_name="openai:gpt-5.2",
            )

    def test_run_image_report_extraction_raises_without_explicit_model(self):
        """Fails fast when caller does not pass a model id."""
        with self.assertRaisesRegex(
            RuntimeError,
            "model_name must be passed explicitly",
        ):
            run_image_report_extraction(
                run_label="Product",
                description="",
                image_urls=[],
                prompt="PROMPT",
            )
