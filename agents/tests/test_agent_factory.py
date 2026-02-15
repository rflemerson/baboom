"""Tests for LLM model factory routing."""

from unittest.mock import patch

from django.test import SimpleTestCase

from agents.brain.agent_factory import get_model


class TestAgentFactory(SimpleTestCase):
    """Tests for provider-to-model mapping."""

    @patch("agents.brain.agent_factory.GroqModel", return_value="groq-model")
    def test_get_model_uses_groq_provider(self, mock_model):
        """Builds Groq model when provider prefix is groq."""
        result = get_model("groq:llama")
        self.assertEqual(result, "groq-model")
        mock_model.assert_called_once_with("llama")

    @patch("agents.brain.agent_factory.OpenAIModel", return_value="openai-model")
    def test_get_model_uses_openai_provider(self, mock_model):
        """Builds OpenAI model when provider prefix is openai."""
        result = get_model("openai:gpt-4o-mini")
        self.assertEqual(result, "openai-model")
        mock_model.assert_called_once_with("gpt-4o-mini")

    @patch("agents.brain.agent_factory.GeminiModel", return_value="gemini-model")
    def test_get_model_uses_gemini_aliases(self, mock_model):
        """Builds Gemini model for gemini/google-gla prefixes."""
        result_one = get_model("gemini:gemini-2.0-flash")
        result_two = get_model("google-gla:gemini-2.0-flash")
        self.assertEqual(result_one, "gemini-model")
        self.assertEqual(result_two, "gemini-model")
        self.assertEqual(mock_model.call_count, 2)

    def test_get_model_returns_raw_name_for_unknown_provider(self):
        """Returns model string for unknown provider as safe fallback."""
        result = get_model("custom-provider:model-x")
        self.assertEqual(result, "model-x")
