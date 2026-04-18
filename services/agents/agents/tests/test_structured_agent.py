"""Tests for structured extraction agent behavior."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from agents.brain import run_structured_extraction
from agents.schemas import ExtractedProduct


class TestStructuredAgent(TestCase):
    """Tests for structured extraction wrapper."""

    @patch("agents.brain.Agent")
    def test_run_structured_extraction_builds_agent_with_expected_output_schema(
        self,
        mock_agent_cls,
    ):
        """Builds Agent using ExtractedProduct output type."""
        agent = MagicMock()
        expected = ExtractedProduct(name="Product")
        agent.run_sync.return_value = type("R", (), {"output": expected})()
        mock_agent_cls.return_value = agent

        result = run_structured_extraction(
            "RAW",
            prompt="PROMPT",
            model_name="gemini:model",
        )

        self.assertEqual(result, expected)
        mock_agent_cls.assert_called_once()
        self.assertEqual(mock_agent_cls.call_args.args[0], "gemini:model")
        kwargs = mock_agent_cls.call_args.kwargs
        self.assertIs(kwargs["output_type"], ExtractedProduct)
        self.assertEqual(kwargs["system_prompt"], "PROMPT")

    @patch("agents.brain.Agent")
    def test_run_structured_extraction_returns_output(self, mock_agent_cls):
        """Returns parsed schema from Agent run output."""
        agent = MagicMock()
        expected = ExtractedProduct(name="Product")
        agent.run_sync.return_value = type("R", (), {"output": expected})()
        mock_agent_cls.return_value = agent

        result = run_structured_extraction(
            "RAW",
            prompt="PROMPT",
            model_name="openai:gpt-5.2",
        )
        self.assertEqual(result, expected)

    @patch("agents.brain.Agent")
    def test_run_structured_extraction_raises_on_error(self, mock_agent_cls):
        """Re-raises exceptions when structured extraction fails."""
        agent = MagicMock()
        agent.run_sync.side_effect = RuntimeError("bad-structured")
        mock_agent_cls.return_value = agent

        with self.assertRaisesRegex(RuntimeError, "bad-structured"):
            run_structured_extraction(
                "RAW",
                prompt="PROMPT",
                model_name="openai:gpt-5.2",
            )

    def test_run_structured_extraction_raises_without_explicit_model(self):
        """Fails fast when caller does not pass a model id."""
        with self.assertRaisesRegex(
            RuntimeError,
            "model_name must be passed explicitly",
        ):
            run_structured_extraction("RAW", prompt="PROMPT")
