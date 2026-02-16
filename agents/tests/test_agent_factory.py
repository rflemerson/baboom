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

    @patch("agents.brain.agent_factory.GoogleModel", return_value="google-model")
    def test_get_model_uses_gemini_aliases(self, mock_model):
        """Builds Gemini model for gemini/google-gla prefixes."""
        result_one = get_model("gemini:gemini-2.0-flash")
        result_two = get_model("google-gla:gemini-2.0-flash")
        self.assertEqual(result_one, "google-model")
        self.assertEqual(result_two, "google-model")
        self.assertEqual(mock_model.call_count, 2)
        for call in mock_model.call_args_list:
            self.assertEqual(call.args[0], "gemini-2.0-flash")
            self.assertIn("provider", call.kwargs)

    @patch("agents.brain.agent_factory.GoogleModel", return_value="google-model")
    def test_get_model_uses_google_alias(self, mock_model):
        """Builds Google model for explicit google provider alias."""
        result = get_model("google:gemini-2.0-flash")
        self.assertEqual(result, "google-model")
        self.assertEqual(mock_model.call_count, 1)
        self.assertEqual(mock_model.call_args.args[0], "gemini-2.0-flash")
        self.assertIn("provider", mock_model.call_args.kwargs)

    def test_get_model_returns_raw_name_for_unknown_provider(self):
        """Returns model string for unknown provider as safe fallback."""
        result = get_model("custom-provider:model-x")
        self.assertEqual(result, "model-x")

    @patch("agents.brain.agent_factory.GroqModel", return_value="groq-model")
    def test_get_model_normalizes_provider_case_and_whitespace(self, mock_model):
        """Normalizes provider prefix and trims model identifiers."""
        result = get_model("  GrOq : llama-3  ")
        self.assertEqual(result, "groq-model")
        mock_model.assert_called_once_with("llama-3")

    @patch.dict("os.environ", {"LLM_MODEL": "openai:gpt-4o-mini"})
    @patch("agents.brain.agent_factory.OpenAIModel", return_value="openai-model")
    def test_get_model_uses_env_when_argument_missing(self, mock_model):
        """Uses LLM_MODEL env var when model_id is not provided."""
        result = get_model(None)
        self.assertEqual(result, "openai-model")
        mock_model.assert_called_once_with("gpt-4o-mini")

    @patch("agents.brain.agent_factory.GroqModel", return_value="groq-model")
    def test_get_model_fills_missing_model_name_with_default(self, mock_model):
        """Uses provider-specific default when model name is empty."""
        result = get_model("groq:")
        self.assertEqual(result, "groq-model")
        mock_model.assert_called_once_with("llama-3.3-70b-versatile")
