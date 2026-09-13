"""Read a skill directory and hand back only what belongs to it."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "skills"
SKILL_FILENAME = "SKILL.md"
MAX_FILE_BYTES = 256 * 1024


class SkillError(Exception):
    """A skill or one of its files could not be served."""


@dataclass(frozen=True)
class SkillFile:
    """One readable file inside a skill directory."""

    path: str
    text: str

    @property
    def digest(self) -> str:
        """Hex digest of the file's bytes."""
        return hashlib.sha256(self.text.encode()).hexdigest()


@dataclass(frozen=True)
class Skill:
    """A skill's frontmatter, body, and the files beside it."""

    slug: str
    name: str
    description: str
    body: str
    files: tuple[str, ...]

    @property
    def digest(self) -> str:
        """Hex digest of the skill document."""
        return hashlib.sha256(self.body.encode()).hexdigest()


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        msg = f"{SKILL_FILENAME} must open with YAML frontmatter"
        raise SkillError(msg)
    _, raw, body = text.split("---\n", 2)
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            msg = f"Unparseable frontmatter line: {line!r}"
            raise SkillError(msg)
        fields[key.strip()] = value.strip()
    for required in ("name", "description"):
        if not fields.get(required):
            msg = f"Frontmatter is missing {required!r}"
            raise SkillError(msg)
    return fields, body.lstrip("\n")


def _resolve(slug: str, relative: str) -> Path:
    """Resolve a path inside one skill, refusing anything that leaves it.

    ``Path.resolve`` follows symlinks, so a link pointing outside the skill
    fails the containment check like any other escape.
    """
    base = (ROOT / slug).resolve()
    if base.parent != ROOT or not base.is_dir():
        msg = f"Unknown skill {slug!r}"
        raise SkillError(msg)
    target = (base / relative).resolve()
    if target != base and base not in target.parents:
        msg = f"{relative!r} is outside skill {slug!r}"
        raise SkillError(msg)
    if not target.is_file():
        msg = f"No file {relative!r} in skill {slug!r}"
        raise SkillError(msg)
    return target


def _read(path: Path, slug: str) -> str:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        msg = f"{path.name} in skill {slug!r} is {size} bytes, over the limit"
        raise SkillError(msg)
    return path.read_text()


def available() -> tuple[str, ...]:
    """Slugs of every skill packaged here."""
    return tuple(
        sorted(
            directory.name
            for directory in ROOT.iterdir()
            if directory.is_dir() and (directory / SKILL_FILENAME).is_file()
        ),
    )


def load(slug: str) -> Skill:
    """Load one skill's document and list the files beside it."""
    document = _resolve(slug, SKILL_FILENAME)
    fields, body = _parse_frontmatter(_read(document, slug))
    base = document.parent
    files = tuple(
        sorted(
            str(candidate.relative_to(base))
            for candidate in base.rglob("*")
            if candidate.is_file() and candidate.name != SKILL_FILENAME
        ),
    )
    return Skill(
        slug=slug,
        name=fields["name"],
        description=fields["description"],
        body=body,
        files=files,
    )


def load_file(slug: str, relative: str) -> SkillFile:
    """Load one supporting file from inside a skill."""
    path = _resolve(slug, relative)
    return SkillFile(path=relative, text=_read(path, slug))
