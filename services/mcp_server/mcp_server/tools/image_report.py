"""Local vision reports for downloaded nutrition-label images."""

from __future__ import annotations

import os
from pathlib import Path

from google import genai
from google.genai import types

from .images import load_image_manifest

PACKAGE_DIR = Path(__file__).resolve().parents[1]


def prompt_path() -> Path:
    """Return the bundled image-analysis prompt path."""
    return PACKAGE_DIR / "prompts" / "image_report.md"


def image_report_path(workspace: str | Path) -> Path:
    """Return the report path below ``workspace``."""
    path = Path(workspace).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path / "image_report.md"


def save_image_report(workspace: str | Path, report: str) -> None:
    """Persist a generated report below ``workspace``."""
    image_report_path(workspace).write_text(report, encoding="utf-8")


def load_image_report(workspace: str | Path) -> str:
    """Load a report from ``workspace`` when one exists."""
    path = image_report_path(workspace)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def create_image_report(workspace: str | Path) -> dict[str, object]:
    """Analyze downloaded images with Gemini and save the resulting report."""
    if os.getenv("VISION_PROVIDER", "gemini") != "gemini":
        message = "VISION_PROVIDER is not supported."
        raise RuntimeError(message)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        message = "GEMINI_API_KEY is not configured."
        raise RuntimeError(message)
    downloaded: list[dict[str, str]] = list(
        load_image_manifest(workspace).get("downloaded", []),
    )
    if not downloaded:
        return {"ok": False, "error": "No images downloaded."}

    prompt = prompt_path().read_text(encoding="utf-8")
    parts = [types.Part.from_text(text=prompt)]
    parts.extend(
        types.Part.from_bytes(
            data=Path(image["path"]).read_bytes(),
            mime_type=image.get("contentType") or "image/jpeg",
        )
        for image in downloaded
    )
    response = genai.Client(api_key=api_key).models.generate_content(
        model=os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash"),
        contents=[types.Content(role="user", parts=parts)],
    )
    report = response.text or ""
    save_image_report(workspace, report)
    return {
        "ok": True,
        "report": report,
        "imageCount": len(downloaded),
        "path": str(image_report_path(workspace)),
    }
