"""Image-selection helpers used before multimodal OCR extraction."""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

ALT_HINT_PREVIEW_MAX = 140
ALT_HINT_PREVIEW_TRUNCATE = 137
FOCUS_TOKEN_MIN_LENGTH = 3
MIN_RELEVANCE_HIGH = 2
MIN_RELEVANCE_LOW = 1
NUTRITION_SIGNAL_THRESHOLD = 3


def candidate_nutrition_signal(candidate: dict) -> int:
    """Score a candidate by likely nutritional-table signals."""
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
    signal += 2 * sum(1 for keyword in strong_keywords if keyword in metadata_text)
    signal += sum(1 for keyword in strong_keywords if keyword in url_text)
    return signal


def tokenize_focus_text(text: str) -> set[str]:
    """Tokenize product and URL hints used to rank relevant images."""
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
    return {
        token
        for token in tokens
        if len(token) >= FOCUS_TOKEN_MIN_LENGTH and token not in stop_words
    }


def candidate_product_relevance(candidate: dict, focus_tokens: set[str]) -> int:
    """Score how relevant an image candidate is to the focused product."""
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


def file_sort_key(file_name: str) -> int:
    """Sort persisted image files by extracted page order."""
    match = re.search(r"image_(\d+)", file_name)
    if not match:
        return 10**9
    return int(match.group(1))


def is_potential_table_candidate(candidate: dict) -> bool:
    """Return whether a candidate likely contains a nutrition table."""
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
    if any(keyword in text for keyword in table_keywords):
        return True
    return candidate_nutrition_signal(candidate) >= NUTRITION_SIGNAL_THRESHOLD


def infer_candidate_kind(candidate: dict) -> str:
    """Infer a human-readable kind for image sequence context."""
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
    if candidate_nutrition_signal(candidate) >= NUTRITION_SIGNAL_THRESHOLD or any(
        keyword in text for keyword in nutrition_keywords
    ):
        return "NUTRITION_TABLE"
    if text:
        return "PRODUCT_IMAGE"
    return "UNKNOWN"


def build_image_sequence_context(
    candidates: list[dict],
    image_paths: list[str],
) -> str:
    """Build prompt context describing the chosen image sequence."""
    if not image_paths:
        return ""
    by_file = {
        str(candidate.get("file")): candidate
        for candidate in candidates
        if candidate.get("file")
    }
    lines: list[str] = []
    for idx, path in enumerate(image_paths, start=1):
        _bucket, file_name = path.split("/", 1)
        candidate = by_file.get(file_name, {})
        metadata = candidate.get("metadata") or {}
        alt = str(metadata.get("alt") or metadata.get("title") or "").strip()
        if len(alt) > ALT_HINT_PREVIEW_MAX:
            alt = f"{alt[:ALT_HINT_PREVIEW_TRUNCATE]}..."
        kind = infer_candidate_kind(candidate)
        lines.append(f"{idx}. kind={kind} file={file_name} hint={alt or '-'}")
    return (
        "\n\n[IMAGE_SEQUENCE_CONTEXT]\n"
        "The sequence below follows the submitted gallery/carousel order. "
        "If there are multiple nutrition tables, map each table to the correct "
        "product/variant using proximity and flavor/plain cues.\n" + "\n".join(lines)
    )


def select_images_for_ocr(
    candidates: list[dict],
    bucket: str,
    product_name: str = "",
    page_url: str = "",
) -> list[str]:
    """Select a stable list of OCR image paths from ranked candidates."""
    max_total = int(os.getenv("OCR_MAX_IMAGES", "12"))
    max_nutrition = int(os.getenv("OCR_MAX_NUTRITION_IMAGES", "8"))
    max_if_no_nutrition = int(os.getenv("OCR_MAX_IMAGES_NO_NUTRITION", "16"))
    max_table_candidates = int(os.getenv("OCR_MAX_TABLE_CANDIDATES", "24"))
    include_all_tables = os.getenv("OCR_INCLUDE_ALL_TABLES", "1") == "1"
    max_nutrition = min(max_nutrition, max_total)

    valid = [
        candidate
        for candidate in candidates
        if int(candidate.get("score", 0)) > 0 and candidate.get("file")
    ]
    url_path = urlparse(page_url).path if page_url else ""
    focus_tokens = tokenize_focus_text(f"{product_name} {url_path}")
    valid = _apply_focus_filter(valid, focus_tokens)
    valid.sort(
        key=lambda candidate: (
            candidate_product_relevance(candidate, focus_tokens),
            int(candidate.get("score", 0)),
        ),
        reverse=True,
    )

    nutrition_candidates = sorted(
        [candidate for candidate in valid if candidate_nutrition_signal(candidate) > 0],
        key=lambda candidate: (
            candidate_nutrition_signal(candidate),
            candidate_product_relevance(candidate, focus_tokens),
            int(candidate.get("score", 0)),
        ),
        reverse=True,
    )

    selected_files: list[str] = []
    seen_files: set[str] = set()
    ordered_files = sorted(
        [str(candidate.get("file")) for candidate in valid if candidate.get("file")],
        key=file_sort_key,
    )

    likely_tables = _collect_likely_tables(
        valid,
        focus_tokens,
        include_all_tables=include_all_tables,
        max_nutrition=max_nutrition,
        max_table_candidates=max_table_candidates,
    )
    _append_candidates(selected_files, seen_files, likely_tables)

    if include_all_tables:
        _add_neighbor_context(selected_files, seen_files, ordered_files)

    _append_candidates(selected_files, seen_files, nutrition_candidates[:max_nutrition])

    target_total = _resolve_target_total(
        selected_files,
        include_all_tables=include_all_tables,
        likely_tables=likely_tables,
        max_total=max_total,
        max_if_no_nutrition=max_if_no_nutrition,
    )
    _fill_remaining_candidates(selected_files, seen_files, valid, target_total)

    return [f"{bucket}/{file_name}" for file_name in selected_files]


def _apply_focus_filter(valid: list[dict], focus_tokens: set[str]) -> list[dict]:
    if not focus_tokens:
        return valid
    with_relevance = [
        (candidate, candidate_product_relevance(candidate, focus_tokens))
        for candidate in valid
    ]
    max_relevance = max((relevance for _, relevance in with_relevance), default=0)
    min_relevance = (
        MIN_RELEVANCE_HIGH if max_relevance >= MIN_RELEVANCE_HIGH else MIN_RELEVANCE_LOW
    )
    focused_candidates = [
        candidate
        for candidate, relevance in with_relevance
        if relevance >= min_relevance
    ]
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
    *,
    include_all_tables: bool,
    max_nutrition: int,
    max_table_candidates: int,
) -> list[dict]:
    likely_tables = [
        candidate for candidate in valid if is_potential_table_candidate(candidate)
    ]
    likely_tables.sort(
        key=lambda candidate: (
            candidate_product_relevance(candidate, focus_tokens),
            candidate_nutrition_signal(candidate),
            -file_sort_key(str(candidate.get("file"))),
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


def _append_candidates(
    selected_files: list[str],
    seen_files: set[str],
    candidates: list[dict],
) -> None:
    for candidate in candidates:
        _append_file_once(selected_files, seen_files, str(candidate["file"]))


def _resolve_target_total(
    selected_files: list[str],
    *,
    include_all_tables: bool,
    likely_tables: list[dict],
    max_total: int,
    max_if_no_nutrition: int,
) -> int:
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
    for candidate in valid:
        if len(selected_files) >= target_total:
            break
        _append_file_once(selected_files, seen_files, str(candidate["file"]))
