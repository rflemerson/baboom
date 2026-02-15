"""Tests for raw extraction agent behavior."""

from unittest.mock import MagicMock, mock_open, patch

from django.test import SimpleTestCase

from agents.brain.raw_extraction_agent import (
    _get_default_prompt,
    run_raw_extraction,
)


class _FakeStorage:
    """Simple storage double for raw extraction tests."""

    def __init__(self, files: dict[str, bytes]):
        self.files = files

    def exists(self, bucket: str, key: str) -> bool:
        """Return if key exists in fake storage."""
        return f"{bucket}/{key}" in self.files

    def download(self, bucket: str, key: str) -> bytes:
        """Download bytes for key."""
        return self.files[f"{bucket}/{key}"]


class TestRawExtractionAgent(SimpleTestCase):
    """Tests for multimodal raw extraction helper."""

    @patch("agents.brain.raw_extraction_agent.os.path.exists", return_value=False)
    def test_default_prompt_fallback(self, _mock_exists):
        """Uses fallback prompt when prompt file does not exist."""
        prompt = _get_default_prompt()
        self.assertEqual(prompt, "Extract product data from images and text.")

    @patch("agents.brain.raw_extraction_agent.os.path.exists", return_value=True)
    @patch(
        "agents.brain.raw_extraction_agent.open",
        new_callable=mock_open,
        read_data="PROMPT",
    )
    def test_default_prompt_from_file(self, _mock_open, _mock_exists):
        """Loads prompt from markdown file when present."""
        prompt = _get_default_prompt()
        self.assertEqual(prompt, "PROMPT")

    @patch("agents.brain.raw_extraction_agent.get_model", return_value="model")
    @patch("agents.brain.raw_extraction_agent.Agent")
    @patch("agents.brain.raw_extraction_agent.get_storage")
    def test_run_raw_extraction_uses_supported_images(
        self,
        mock_get_storage,
        mock_agent_cls,
        _mock_get_model,
    ):
        """Sends prompt text plus only supported image formats to agent."""
        storage = _FakeStorage(
            {
                "1/images/a.jpg": b"img-a",
                "1/images/b.gif": b"img-b",
            }
        )
        mock_get_storage.return_value = storage

        agent = MagicMock()
        agent.run_sync.return_value = type("R", (), {"data": "RAW"})()
        mock_agent_cls.return_value = agent

        result = run_raw_extraction(
            name="Produto",
            description="Descricao",
            image_paths=["1/images/a.jpg", "1/images/b.gif"],
            prompt="PROMPT",
            model_name="google-gla:gemini",
        )

        self.assertEqual(result, "RAW")
        call_args = agent.run_sync.call_args.args[0]
        self.assertEqual(len(call_args), 2)  # text + one supported image

    @patch("agents.brain.raw_extraction_agent.get_model", return_value="model")
    @patch("agents.brain.raw_extraction_agent.Agent")
    @patch("agents.brain.raw_extraction_agent.get_storage")
    def test_run_raw_extraction_returns_output_fallback(
        self,
        mock_get_storage,
        mock_agent_cls,
        _mock_get_model,
    ):
        """Returns .output when .data attribute is not present."""
        mock_get_storage.return_value = _FakeStorage({})

        agent = MagicMock()
        agent.run_sync.return_value = type("R", (), {"output": "RAW-OUT"})()
        mock_agent_cls.return_value = agent

        result = run_raw_extraction(
            name="Produto",
            description="",
            image_paths=[],
        )
        self.assertEqual(result, "RAW-OUT")

    @patch("agents.brain.raw_extraction_agent.get_model", return_value="model")
    @patch("agents.brain.raw_extraction_agent.Agent")
    @patch("agents.brain.raw_extraction_agent.get_storage")
    def test_run_raw_extraction_raises_on_agent_error(
        self,
        mock_get_storage,
        mock_agent_cls,
        _mock_get_model,
    ):
        """Re-raises exceptions from Agent execution."""
        mock_get_storage.return_value = _FakeStorage({})
        agent = MagicMock()
        agent.run_sync.side_effect = RuntimeError("boom")
        mock_agent_cls.return_value = agent

        with self.assertRaisesRegex(RuntimeError, "boom"):
            run_raw_extraction(name="Produto", description="", image_paths=[])
