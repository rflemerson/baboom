import os
from pathlib import Path

from google import genai
from google.genai import types

from .images import load_image_manifest
from .workspace import get_current_item_id, item_dir

SERVICE_DIR = Path(__file__).resolve().parents[2]
PACKAGE_DIR = SERVICE_DIR / "mcp_server"


def prompt_path() -> Path:
    return PACKAGE_DIR / "prompts" / "image_report.md"


def load_image_report_prompt() -> str:
    path = prompt_path()
    return path.read_text(encoding="utf-8")


def image_report_path() -> Path:
    item_id = get_current_item_id()
    if not item_id:
        raise RuntimeError("Nenhum item atual.")
    return item_dir(item_id) / "image_report.md"


def save_image_report(report: str) -> None:
    path = image_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def load_image_report() -> str:
    path = image_report_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def create_image_report() -> dict[str, object]:
    provider = os.getenv("VISION_PROVIDER", "gemini")
    if provider != "gemini":
        raise RuntimeError(f"VISION_PROVIDER não suportado: {provider}")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurado.")

    model = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")

    manifest = load_image_manifest()
    downloaded: list[dict[str, str]] = manifest.get("downloaded", [])

    if not downloaded:
        return {
            "ok": False,
            "error": "Nenhuma imagem baixada. Rode prepare_current_item primeiro.",
        }

    client = genai.Client(api_key=api_key)
    prompt = load_image_report_prompt()

    parts = [types.Part.from_text(text=prompt)]

    for image in downloaded:
        path = Path(image["path"])
        mime_type = image.get("contentType") or "image/jpeg"
        parts.append(
            types.Part.from_bytes(
                data=path.read_bytes(),
                mime_type=mime_type,
            ),
        )

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=parts,
            ),
        ],
    )

    report = response.text or ""
    save_image_report(report)

    return {
        "ok": True,
        "report": report,
        "imageCount": len(downloaded),
        "path": str(image_report_path()),
    }
