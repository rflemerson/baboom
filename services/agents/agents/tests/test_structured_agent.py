"""Tests for structured extraction agent behavior."""

from unittest.mock import MagicMock, mock_open, patch

from agents.brain.structured_agent import (
    _get_default_prompt,
    get_agent,
    run_structured_extraction,
)
from django.test import SimpleTestCase


class TestStructuredAgent(SimpleTestCase):
    """Tests for structured extraction wrapper."""

    @patch("agents.brain.structured_agent.os.path.exists", return_value=False)
    def test_default_prompt_fallback(self, _mock_exists):
        """Uses fallback structured prompt when prompt file is missing."""
        prompt = _get_default_prompt()
        self.assertEqual(prompt, "Convert the following text to structured JSON.")

    @patch("agents.brain.structured_agent.os.path.exists", return_value=True)
    @patch("agents.brain.structured_agent.open", new_callable=mock_open, read_data="P")
    def test_default_prompt_from_file(self, _mock_open, _mock_exists):
        """Reads structured prompt from file when available."""
        prompt = _get_default_prompt()
        self.assertEqual(prompt, "P")

    @patch("agents.brain.structured_agent.get_model", return_value="model")
    @patch("agents.brain.structured_agent.Agent")
    def test_get_agent_builds_agent_with_expected_output_schema(
        self, mock_agent_cls, _mock_get_model
    ):
        """Builds Agent using ProductAnalysisList output type."""
        _agent = get_agent("gemini:model", "PROMPT")
        mock_agent_cls.assert_called_once()
        kwargs = mock_agent_cls.call_args.kwargs
        self.assertEqual(kwargs["system_prompt"], "PROMPT")

    @patch("agents.brain.structured_agent.get_agent")
    def test_run_structured_extraction_returns_output(self, mock_get_agent):
        """Returns parsed schema from Agent run output."""
        agent = MagicMock()
        expected = {"items": [{"name": "Product"}]}
        agent.run_sync.return_value = type("R", (), {"output": expected})()
        mock_get_agent.return_value = agent

        result = run_structured_extraction("RAW", prompt="PROMPT")
        self.assertEqual(result, expected)

    @patch("agents.brain.structured_agent.get_agent")
    def test_run_structured_extraction_raises_on_error(self, mock_get_agent):
        """Re-raises exceptions when structured extraction fails."""
        agent = MagicMock()
        agent.run_sync.side_effect = RuntimeError("bad-structured")
        mock_get_agent.return_value = agent

        with self.assertRaisesRegex(RuntimeError, "bad-structured"):
            run_structured_extraction("RAW")
