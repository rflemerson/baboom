"""Tests for safe MCP skill loading."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch

from django.test import SimpleTestCase

from mcp_server.loader import SkillError, load, load_file

if TYPE_CHECKING:
    from collections.abc import Callable

EXPECTED_SKILL_NAME = "product-curation"


def _skill_error(action: Callable[[], object]) -> SkillError:
    """Return the expected loader error, failing if the action succeeds."""
    try:
        action()
    except SkillError as error:
        return error
    raise AssertionError


class SkillLoaderTests(SimpleTestCase):
    """Verify skill files cannot escape their packaged directory."""

    def test_parent_relative_file_is_refused(self) -> None:
        """A parent traversal raises an outside-skill error."""
        raised = _skill_error(
            lambda: load_file("product-curation", "../settings/base.py"),
        )

        assert "outside" in str(raised)

    def test_absolute_file_is_refused(self) -> None:
        """An absolute path cannot select a file outside the skill."""
        absolute_path = str(Path(__file__).resolve())

        raised = _skill_error(
            lambda: load_file("product-curation", absolute_path),
        )

        assert "outside" in str(raised)

    def test_symlink_that_escapes_skill_is_refused(self) -> None:
        """A symlink resolving outside the skill is rejected."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "temporary-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: Test\ndescription: Test\n---\n")
            outside = root / "outside.txt"
            outside.write_text("outside")
            (skill / "escape.txt").symlink_to(outside)

            with patch("mcp_server.loader.ROOT", root):
                raised = _skill_error(
                    lambda: load_file("temporary-skill", "escape.txt"),
                )

        assert "outside" in str(raised)

    def test_missing_file_is_refused(self) -> None:
        """A missing supporting file raises a descriptive loader error."""
        raised = _skill_error(
            lambda: load_file("product-curation", "missing.txt"),
        )

        assert "No file" in str(raised)

    def test_unknown_skill_is_refused(self) -> None:
        """An unknown skill slug is rejected before file access."""
        raised = _skill_error(lambda: load("not-a-real-skill"))

        assert "Unknown skill" in str(raised)

    def test_skill_document_is_loaded_with_frontmatter(self) -> None:
        """A packaged skill exposes its parsed metadata and body."""
        skill = load("product-curation")

        assert skill.name == EXPECTED_SKILL_NAME
        assert skill.body
        assert "SKILL.md" not in skill.files

    def test_supporting_file_is_loaded(self) -> None:
        """A file beside a skill document is returned with its relative path."""
        skill = load("product-curation")
        relative_path = skill.files[0]

        loaded = load_file("product-curation", relative_path)

        assert loaded.path == relative_path
        assert loaded.text
