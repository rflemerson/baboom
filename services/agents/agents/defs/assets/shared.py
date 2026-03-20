"""Shared helpers for the Dagster page-first ingestion assets."""

import json
import os
import re
from urllib.parse import urlparse

from dagster import Config

NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


class ItemConfig(Config):
    """Configuration for running a specific queued scraped item."""

    item_id: int
    url: str
    store_slug: str = "unknown"


def _slugify(value: str) -> str:
    normalized = NON_ALNUM_PATTERN.sub("-", value.lower()).strip("-")
    return normalized or "item"


def _to_graphql_stock_status(status: str | None) -> str:
    stock_map = {
        "A": "AVAILABLE",
        "L": "LAST_UNITS",
        "O": "OUT_OF_STOCK",
        "AVAILABLE": "AVAILABLE",
        "LAST_UNITS": "LAST_UNITS",
        "OUT_OF_STOCK": "OUT_OF_STOCK",
    }
    return stock_map.get((status or "").upper(), "AVAILABLE")


def _parse_number(value) -> float | None:
    """Parse numbers from LLM/API values like '30g', '1,5', 'N/A'."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    parsed = match.group(0) if match else ""
    if not parsed:
        return None
    try:
        return float(parsed)
    except (TypeError, ValueError):
        return None


def _to_float(value, default: float = 0.0) -> float:
    parsed = _parse_number(value)
    return parsed if parsed is not None else default


def _to_int(value, default: int = 0) -> int:
    parsed = _parse_number(value)
    if parsed is None:
        return default
    return int(parsed)


def _build_nutrition_payload(analysis_data: dict) -> list[dict]:
    nutrition = analysis_data.get("nutrition_facts")
    if not nutrition:
        return []

    micronutrients = [
        {
            "name": m.get("name"),
            "value": _to_float(m.get("value")),
            "unit": m.get("unit") or "mg",
        }
        for m in (nutrition.get("micronutrients") or [])
        if m.get("name")
    ]

    return [
        {
            "flavorNames": analysis_data.get("flavor_names") or [],
            "nutritionFacts": {
                "description": analysis_data.get("variant_name") or "AI Analysis",
                "servingSizeGrams": _to_float(nutrition.get("serving_size_grams")),
                "energyKcal": _to_int(nutrition.get("energy_kcal")),
                "proteins": _to_float(nutrition.get("proteins")),
                "carbohydrates": _to_float(nutrition.get("carbohydrates")),
                "totalSugars": _to_float(nutrition.get("total_sugars")),
                "addedSugars": _to_float(nutrition.get("added_sugars")),
                "totalFats": _to_float(nutrition.get("total_fats")),
                "saturatedFats": _to_float(nutrition.get("saturated_fats")),
                "transFats": _to_float(nutrition.get("trans_fats")),
                "dietaryFiber": _to_float(nutrition.get("dietary_fiber")),
                "sodium": _to_float(nutrition.get("sodium")),
                "micronutrients": micronutrients,
            },
        },
    ]


def _candidate_nutrition_signal(candidate: dict) -> int:
    signal = int(candidate.get("nutrition_signal") or 0)
    metadata = candidate.get("metadata") or {}
    metadata_text = " ".join(
        [
            str(metadata.get("alt") or ""),
            str(metadata.get("title") or ""),
            str(metadata.get("class") or ""),
            str(metadata.get("id") or ""),
        ],
    ).lower()
    url_text = str(candidate.get("url") or "").lower()
    strong_keywords = [
        "tabela",
        "nutricional",
        "nutrition",
        "facts",
        "label",
        "rotulo",
        "tabela_nutricional",
    ]
    signal += 2 * sum(1 for kw in strong_keywords if kw in metadata_text)
    signal += sum(1 for kw in strong_keywords if kw in url_text)
    return signal


def _tokenize_focus_text(text: str) -> set[str]:
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    stop_words = {
        "com",
        "para",
        "sem",
        "the",
        "and",
        "dos",
        "das",
        "de",
        "da",
        "do",
        "barra",
        "nutrition",
        "soldiers",
        "black",
        "skull",
        "produto",
        "products",
        "product",
        "p",
    }
    return {t for t in tokens if len(t) >= 3 and t not in stop_words}


def _candidate_product_relevance(candidate: dict, focus_tokens: set[str]) -> int:
    if not focus_tokens:
        return 0
    metadata = candidate.get("metadata") or {}
    candidate_text = " ".join(
        [
            str(metadata.get("alt") or ""),
            str(metadata.get("title") or ""),
            str(candidate.get("url") or ""),
        ],
    ).lower()
    return sum(1 for token in focus_tokens if token in candidate_text)


def _file_sort_key(file_name: str) -> int:
    match = re.search(r"image_(\d+)", file_name)
    if not match:
        return 10**9
    return int(match.group(1))


def _is_potential_table_candidate(candidate: dict) -> bool:
    cv_threshold = float(os.getenv("OCR_CV_TABLE_THRESHOLD", "0.22"))
    cv_score = float(candidate.get("cv_table_score") or 0.0)
    if cv_score >= cv_threshold:
        return True

    metadata = candidate.get("metadata") or {}
    text = " ".join(
        [
            str(metadata.get("alt") or ""),
            str(metadata.get("title") or ""),
            str(candidate.get("url") or ""),
        ],
    ).lower()
    table_keywords = [
        "tabela",
        "nutricional",
        "nutrition",
        "facts",
        "nutrition-facts",
        "rotulo",
        "label",
        "informacao nutricional",
    ]
    if any(kw in text for kw in table_keywords):
        return True
    # Keep this threshold a bit higher to avoid generic product photos with noisy score.
    return _candidate_nutrition_signal(candidate) >= 3


def _infer_candidate_kind(candidate: dict) -> str:
    metadata = candidate.get("metadata") or {}
    text = " ".join(
        [
            str(metadata.get("alt") or ""),
            str(metadata.get("title") or ""),
            str(candidate.get("url") or ""),
        ],
    ).lower()
    nutrition_keywords = [
        "tabela",
        "nutricional",
        "nutrition",
        "nutrition-facts",
        "facts",
        "rotulo",
        "label",
    ]
    if _candidate_nutrition_signal(candidate) >= 3 or any(
        kw in text for kw in nutrition_keywords
    ):
        return "NUTRITION_TABLE"
    if text:
        return "PRODUCT_IMAGE"
    return "UNKNOWN"


def _build_image_sequence_context(
    candidates: list[dict],
    image_paths: list[str],
) -> str:
    if not image_paths:
        return ""
    by_file = {str(c.get("file")): c for c in candidates if c.get("file")}
    lines: list[str] = []
    for idx, path in enumerate(image_paths, start=1):
        _bucket, file_name = path.split("/", 1)
        candidate = by_file.get(file_name, {})
        metadata = candidate.get("metadata") or {}
        alt = str(metadata.get("alt") or metadata.get("title") or "").strip()
        if len(alt) > 140:
            alt = f"{alt[:137]}..."
        kind = _infer_candidate_kind(candidate)
        lines.append(f"{idx}. kind={kind} file={file_name} hint={alt or '-'}")
    return (
        "\n\n[IMAGE_SEQUENCE_CONTEXT]\n"
        "The sequence below follows the submitted gallery/carousel order. "
        "If there are multiple nutrition tables, map each table to the correct product/variant using proximity and flavor/plain cues.\n"
        + "\n".join(lines)
    )


def _build_json_context_block(title: str, payload: dict | list | None) -> str:
    """Render contextual JSON block for LLM prompts."""
    if not payload:
        return ""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(body) > 7000:
        body = f"{body[:7000]}..."
    return f"\n\n[{title}]\n{body}\n[/{title}]"


def _extract_expected_variant_signals(raw_text: str) -> set[str]:
    """Extract flavor/variant hints from OCR text for consistency checks."""
    signals: set[str] = set()
    if not raw_text:
        return signals

    for match in re.findall(r"(?im)^\s*[-*]\s*([^\n]{2,80})\s*$", raw_text):
        line = match.strip(" -:*")
        if not line:
            continue
        lowered = line.lower()
        if lowered in {
            "not specified in the provided images or text.",
        }:
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


def _count_structured_variant_signals(payload: dict) -> int:
    """Count how many variants/flavors structured extraction captured."""
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


def _build_reconciliation_prompt(expected_variants: int) -> str:
    """Prompt forcing strict variant/table reconciliation."""
    return (
        "Convert the raw text into strict structured JSON.\n"
        "Goal: do not miss variants/flavors/nutrition tables.\n"
        f"We detected approximately {expected_variants} variants in the OCR text.\n"
        "Mandatory rules:\n"
        "1) If there is more than one table/flavor, return one item per variant.\n"
        "2) Fill `variant_name`, `flavor_names`, and `is_variant=true` when applicable.\n"
        "3) Do not collapse different flavors into the same item.\n"
        "4) If a table has no explicit flavor, use a descriptive variant name.\n"
        "5) Keep the schema valid."
    )


def _extract_context_block(raw_text: str, block_name: str) -> dict | None:
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
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _normalize_flavor_token(value: str) -> str:
    return NON_ALNUM_PATTERN.sub(" ", value.lower()).strip()


def _extract_allowed_variants_from_scraper_context(
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


def _add_allowed_variant_token(allowed: set[str], value) -> None:
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


def _count_invalid_variant_tokens(payload: dict, allowed_variants: set[str]) -> int:
    """Count extracted flavor/variant tokens not present in allowed context."""
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
    """Count invalid variant tokens for a single extracted item."""
    return sum(
        1
        for token in _item_variant_tokens(item)
        if _is_invalid_variant_token(token, allowed_variants)
    )


def _item_variant_tokens(item: dict) -> list[str]:
    """Collect normalized variant/flavor tokens from one extracted item."""
    raw_values: list[str] = []
    variant_name = item.get("variant_name")
    if variant_name:
        raw_values.append(str(variant_name))
    for flavor in item.get("flavor_names") or []:
        raw_values.append(str(flavor))
    return [token for value in raw_values if (token := _normalize_flavor_token(value))]


def _is_invalid_variant_token(token: str, allowed_variants: set[str]) -> bool:
    """Return True when one token is outside the allowed variant set."""
    if token in allowed_variants:
        return False
    return not any(token in allowed or allowed in token for allowed in allowed_variants)


def _build_context_guard_prompt(allowed_variants: set[str]) -> str:
    allowed_list = ", ".join(sorted(allowed_variants))
    return (
        "Convert the raw text to structured JSON while respecting page context.\n"
        "Use only flavors/variants present in the allowed list.\n"
        f"Allowed variants: {allowed_list}\n"
        "If mapping is unclear, keep the item without invented flavors.\n"
        "Keep the schema valid."
    )


def _apply_focus_filter(valid: list[dict], focus_tokens: set[str]) -> list[dict]:
    if not focus_tokens:
        return valid
    with_relevance = [(c, _candidate_product_relevance(c, focus_tokens)) for c in valid]
    max_relevance = max((rel for _, rel in with_relevance), default=0)
    min_relevance = 2 if max_relevance >= 2 else 1
    focused_candidates = [c for c, rel in with_relevance if rel >= min_relevance]
    return focused_candidates or valid


def _append_file_once(
    selected_files: list[str],
    seen_files: set[str],
    file_name: str,
) -> None:
    if file_name in seen_files:
        return
    selected_files.append(file_name)
    seen_files.add(file_name)


def _collect_likely_tables(
    valid: list[dict],
    focus_tokens: set[str],
    include_all_tables: bool,
    max_nutrition: int,
    max_table_candidates: int,
) -> list[dict]:
    likely_tables = [c for c in valid if _is_potential_table_candidate(c)]
    likely_tables.sort(
        key=lambda x: (
            _candidate_product_relevance(x, focus_tokens),
            _candidate_nutrition_signal(x),
            -_file_sort_key(str(x.get("file"))),
        ),
        reverse=True,
    )
    table_limit = max_table_candidates if include_all_tables else max_nutrition
    return likely_tables[:table_limit]


def _add_neighbor_context(
    selected_files: list[str],
    seen_files: set[str],
    ordered_files: list[str],
) -> None:
    file_to_pos = {file_name: idx for idx, file_name in enumerate(ordered_files)}
    for file_name in selected_files.copy():
        pos = file_to_pos.get(file_name)
        if pos is None:
            continue
        for neighbor_pos in [pos - 1, pos + 1]:
            if neighbor_pos < 0 or neighbor_pos >= len(ordered_files):
                continue
            _append_file_once(selected_files, seen_files, ordered_files[neighbor_pos])


def _select_images_for_ocr(
    candidates: list[dict],
    bucket: str,
    product_name: str = "",
    page_url: str = "",
) -> list[str]:
    max_total = int(os.getenv("OCR_MAX_IMAGES", "12"))
    max_nutrition = int(os.getenv("OCR_MAX_NUTRITION_IMAGES", "8"))
    max_if_no_nutrition = int(os.getenv("OCR_MAX_IMAGES_NO_NUTRITION", "16"))
    max_table_candidates = int(os.getenv("OCR_MAX_TABLE_CANDIDATES", "24"))
    include_all_tables = os.getenv("OCR_INCLUDE_ALL_TABLES", "1") == "1"
    max_nutrition = min(max_nutrition, max_total)

    valid = [c for c in candidates if int(c.get("score", 0)) > 0 and c.get("file")]
    url_path = urlparse(page_url).path if page_url else ""
    focus_tokens = _tokenize_focus_text(f"{product_name} {url_path}")
    valid = _apply_focus_filter(valid, focus_tokens)
    valid.sort(
        key=lambda x: (
            _candidate_product_relevance(x, focus_tokens),
            int(x.get("score", 0)),
        ),
        reverse=True,
    )

    nutrition_candidates = sorted(
        [c for c in valid if _candidate_nutrition_signal(c) > 0],
        key=lambda x: (
            _candidate_nutrition_signal(x),
            _candidate_product_relevance(x, focus_tokens),
            int(x.get("score", 0)),
        ),
        reverse=True,
    )

    selected_files: list[str] = []
    seen_files: set[str] = set()
    ordered_files = sorted(
        [str(c.get("file")) for c in valid if c.get("file")],
        key=_file_sort_key,
    )

    likely_tables = _collect_likely_tables(
        valid,
        focus_tokens,
        include_all_tables,
        max_nutrition,
        max_table_candidates,
    )
    _append_candidates(selected_files, seen_files, likely_tables)

    if include_all_tables:
        _add_neighbor_context(selected_files, seen_files, ordered_files)

    _append_candidates(selected_files, seen_files, nutrition_candidates[:max_nutrition])

    target_total = _resolve_target_total(
        selected_files,
        include_all_tables,
        likely_tables,
        max_total,
        max_if_no_nutrition,
    )
    _fill_remaining_candidates(selected_files, seen_files, valid, target_total)

    return [f"{bucket}/{file_name}" for file_name in selected_files]


def _append_candidates(
    selected_files: list[str],
    seen_files: set[str],
    candidates: list[dict],
) -> None:
    """Append candidate files once, preserving original order."""
    for candidate in candidates:
        _append_file_once(selected_files, seen_files, str(candidate["file"]))


def _resolve_target_total(
    selected_files: list[str],
    include_all_tables: bool,
    likely_tables: list[dict],
    max_total: int,
    max_if_no_nutrition: int,
) -> int:
    """Resolve final number of images to send for OCR."""
    target_total = max_total if selected_files else max_if_no_nutrition
    if include_all_tables and likely_tables:
        target_total = max(target_total, len(selected_files))
    return target_total


def _fill_remaining_candidates(
    selected_files: list[str],
    seen_files: set[str],
    valid: list[dict],
    target_total: int,
) -> None:
    """Fill remaining OCR slots with best-scoring valid candidates."""
    for candidate in valid:
        if len(selected_files) >= target_total:
            break
        _append_file_once(selected_files, seen_files, str(candidate["file"]))
