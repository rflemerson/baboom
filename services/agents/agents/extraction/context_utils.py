"""Context and prompt helpers used by the extraction stage."""

from __future__ import annotations

import json
import re

CONTEXT_BLOCK_CHAR_LIMIT = 7000


def build_json_context_block(title: str, payload: dict | list | None) -> str:
    """Render contextual JSON block for LLM prompts."""
    if not payload:
        return ""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(body) > CONTEXT_BLOCK_CHAR_LIMIT:
        body = f"{body[:CONTEXT_BLOCK_CHAR_LIMIT]}..."
    return f"\n\n[{title}]\n{body}\n[/{title}]"


def extract_expected_variant_signals(raw_text: str) -> set[str]:
    """Extract flavor and variant hints from OCR text for consistency checks."""
    signals: set[str] = set()
    if not raw_text:
        return signals

    for match in re.findall(r"(?im)^\s*[-*]\s*([^\n]{2,80})\s*$", raw_text):
        line = match.strip(" -:*")
        if not line:
            continue
        lowered = line.lower()
        if lowered in {"not specified in the provided images or text."}:
            continue
        if any(
            token in lowered
            for token in [
                "amendoim",
                "avel",
                "cookies",
                "chocolate",
                "baunilha",
                "morango",
                "coco",
                "frutas",
            ]
        ):
            signals.add(line)

    for match in re.findall(r"(?i)referente a\s+([^)\\n]+)", raw_text):
        label = re.sub(r"\s+", " ", match).strip(" .:-")
        if label:
            signals.add(label)

    for match in re.findall(
        r"(?i)\b(?:sabor|flavor|variante|variation)\b[:\s-]+([^\n,;]{2,80})",
        raw_text,
    ):
        label = re.sub(r"\s+", " ", match).strip(" .:-")
        if label:
            signals.add(label)

    return signals


def count_structured_variant_signals(payload: dict) -> int:
    """Count how many variants or flavors structured extraction captured."""
    items = payload.get("items") or []
    variant_names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        variant_name = str(item.get("variant_name") or "").strip()
        if variant_name:
            variant_names.add(variant_name.lower())
        for flavor in item.get("flavor_names") or []:
            flavor_name = str(flavor).strip()
            if flavor_name:
                variant_names.add(flavor_name.lower())
    return max(len(items), len(variant_names))


def build_reconciliation_prompt(expected_variants: int) -> str:
    """Prompt forcing strict variant and table reconciliation."""
    return (
        "Convert the raw text into strict structured JSON.\n"
        "Goal: do not miss variants/flavors/nutrition tables.\n"
        f"We detected approximately {expected_variants} variants in the OCR text.\n"
        "Mandatory rules:\n"
        "1) If there is more than one table/flavor, return one item per variant.\n"
        "2) Fill `variant_name`, `flavor_names`, and `is_variant=true` "
        "when applicable.\n"
        "3) Do not collapse different flavors into the same item.\n"
        "4) If a table has no explicit flavor, use a descriptive variant name.\n"
        "5) Keep the schema valid."
    )


def extract_context_block(raw_text: str, block_name: str) -> dict | None:
    """Extract JSON payload from contextual block embedded in raw text."""
    pattern = rf"\[{re.escape(block_name)}\]\s*(.*?)\s*\[/{re.escape(block_name)}\]"
    match = re.search(pattern, raw_text, flags=re.DOTALL)
    if not match:
        return None
    block_text = match.group(1).strip()
    if not block_text or block_text.endswith("..."):
        return None
    try:
        payload = json.loads(block_text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_flavor_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def extract_allowed_variants_from_scraper_context(
    scraper_context: dict | None,
) -> set[str]:
    """Build allowed variant token set from normalized scraper context."""
    if not scraper_context:
        return set()

    platform = str(scraper_context.get("platform") or "").lower()
    if "shopify" in platform:
        return _extract_allowed_variants_from_shopify_context(scraper_context)
    if "vtex" in platform:
        return _extract_allowed_variants_from_vtex_context(scraper_context)
    return set()


def _add_allowed_variant_token(allowed: set[str], value: object) -> None:
    if value is None:
        return
    token = _normalize_flavor_token(str(value))
    if token:
        allowed.add(token)


def _extract_allowed_variants_from_shopify_context(scraper_context: dict) -> set[str]:
    allowed: set[str] = set()
    for option in scraper_context.get("options") or []:
        if not isinstance(option, dict):
            continue
        for value in option.get("values") or []:
            _add_allowed_variant_token(allowed, value)

    for variant in scraper_context.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        for key in ("option1", "option2", "option3", "title", "name"):
            _add_allowed_variant_token(allowed, variant.get(key))
    return allowed


def _extract_allowed_variants_from_vtex_context(scraper_context: dict) -> set[str]:
    allowed: set[str] = set()
    for sku_item in scraper_context.get("items") or []:
        if not isinstance(sku_item, dict):
            continue
        for key in ("name", "complementName"):
            _add_allowed_variant_token(allowed, sku_item.get(key))
        for variation in sku_item.get("variations") or []:
            _add_allowed_variant_token(allowed, variation)
    return allowed


def count_invalid_variant_tokens(payload: dict, allowed_variants: set[str]) -> int:
    """Count extracted flavor tokens not present in allowed scraper context."""
    if not allowed_variants:
        return 0
    invalid = 0
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        invalid += _count_item_invalid_variant_tokens(item, allowed_variants)
    return invalid


def _count_item_invalid_variant_tokens(
    item: dict,
    allowed_variants: set[str],
) -> int:
    return sum(
        1
        for token in _item_variant_tokens(item)
        if _is_invalid_variant_token(token, allowed_variants)
    )


def _item_variant_tokens(item: dict) -> list[str]:
    raw_values: list[str] = []
    variant_name = item.get("variant_name")
    if variant_name:
        raw_values.append(str(variant_name))
    raw_values.extend(str(flavor) for flavor in (item.get("flavor_names") or []))
    return [token for value in raw_values if (token := _normalize_flavor_token(value))]


def _is_invalid_variant_token(token: str, allowed_variants: set[str]) -> bool:
    if token in allowed_variants:
        return False
    return not any(token in allowed or allowed in token for allowed in allowed_variants)


def build_context_guard_prompt(allowed_variants: set[str]) -> str:
    """Prompt forcing the model to stay inside the allowed variant set."""
    allowed_list = ", ".join(sorted(allowed_variants))
    return (
        "Convert the raw text to structured JSON while respecting page context.\n"
        "Use only flavors/variants present in the allowed list.\n"
        f"Allowed variants: {allowed_list}\n"
        "If mapping is unclear, keep the item without invented flavors.\n"
        "Keep the schema valid."
    )
