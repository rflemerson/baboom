"""Dagster assets for the page-first product ingestion pipeline."""

import json
import os
import re
from urllib.parse import urlparse

from dagster import AssetExecutionContext, Config, MetadataValue, asset

from .brain.raw_extraction_agent import run_raw_extraction
from .brain.structured_agent import run_structured_extraction
from .resources import AgentClientResource, ScraperServiceResource, StorageResource
from .schemas.product import RawScrapedData


class ItemConfig(Config):
    """Configuration for running a specific queued scraped item."""

    item_id: int
    url: str
    store_slug: str = "unknown"


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
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
        }
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
        ]
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
        ]
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
        ]
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
        ]
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
    candidates: list[dict], image_paths: list[str]
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
        "A ordem abaixo segue o carrossel/seleção enviada. "
        "Se houver varias tabelas, associe cada tabela ao produto/variante correto pela proximidade e sinais de sabor/natural.\n"
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
            "não especificado nas imagens ou texto fornecidos.",
            "nao especificado nas imagens ou texto fornecidos.",
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
        r"(?i)\b(?:sabor|flavor|variante|variation)\b[:\s-]+([^\n,;]{2,80})", raw_text
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
        "Converta o texto bruto para JSON estruturado rigoroso.\n"
        "Objetivo: nao perder variantes/sabores/tabelas nutricionais.\n"
        f"Detectamos aproximadamente {expected_variants} variantes no texto OCR.\n"
        "Regras obrigatorias:\n"
        "1) Se houver mais de uma tabela/sabor, retorne um item por variante.\n"
        "2) Preencha `variant_name`, `flavor_names` e `is_variant=true` quando aplicavel.\n"
        "3) Nao colapse sabores diferentes no mesmo item.\n"
        "4) Se alguma tabela nao tiver sabor explicito, use um nome descritivo de variante.\n"
        "5) Mantenha schema valido."
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
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _extract_allowed_flavors_from_catalog(catalog_context: dict | None) -> set[str]:
    """Build allowed flavor set from catalog context options/variants."""
    if not catalog_context:
        return set()
    allowed: set[str] = set()

    for option in catalog_context.get("options") or []:
        if not isinstance(option, dict):
            continue
        option_name = str(option.get("name") or "").lower()
        if "sabor" not in option_name and "flavor" not in option_name:
            continue
        for value in option.get("values") or []:
            token = _normalize_flavor_token(str(value))
            if token:
                allowed.add(token)

    for variant in catalog_context.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        for key in ("option1", "option2", "option3", "title", "name"):
            value = variant.get(key)
            if value:
                token = _normalize_flavor_token(str(value))
                if token:
                    allowed.add(token)

    return allowed


def _count_invalid_catalog_flavors(payload: dict, allowed_flavors: set[str]) -> int:
    """Count extracted flavor tokens that do not exist in catalog context."""
    if not allowed_flavors:
        return 0
    invalid = 0
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        candidates: list[str] = []
        variant_name = item.get("variant_name")
        if variant_name:
            candidates.append(str(variant_name))
        for flavor in item.get("flavor_names") or []:
            candidates.append(str(flavor))
        for value in candidates:
            token = _normalize_flavor_token(value)
            if not token:
                continue
            if token not in allowed_flavors and not any(
                token in allowed or allowed in token for allowed in allowed_flavors
            ):
                invalid += 1
    return invalid


def _build_catalog_guard_prompt(allowed_flavors: set[str]) -> str:
    allowed_list = ", ".join(sorted(allowed_flavors))
    return (
        "Converta o texto bruto para JSON estruturado, obedecendo o catálogo.\n"
        "Use somente sabores/variantes presentes na lista permitida.\n"
        f"Sabores permitidos: {allowed_list}\n"
        "Se não houver mapeamento claro, mantenha item sem flavor inventado.\n"
        "Mantenha schema válido."
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
    selected_files: list[str], seen_files: set[str], file_name: str
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
    selected_files: list[str], seen_files: set[str], ordered_files: list[str]
) -> None:
    file_to_pos = {file_name: idx for idx, file_name in enumerate(ordered_files)}
    for file_name in list(selected_files):
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
    for c in likely_tables:
        _append_file_once(selected_files, seen_files, str(c["file"]))

    if include_all_tables:
        _add_neighbor_context(selected_files, seen_files, ordered_files)

    for c in nutrition_candidates[:max_nutrition]:
        _append_file_once(selected_files, seen_files, str(c["file"]))

    target_total = max_total if selected_files else max_if_no_nutrition
    if include_all_tables and likely_tables:
        target_total = max(target_total, len(selected_files))
    for c in valid:
        if len(selected_files) >= target_total:
            break
        _append_file_once(selected_files, seen_files, str(c["file"]))

    return [f"{bucket}/{file_name}" for file_name in selected_files]


@asset
def downloaded_assets(
    context: AssetExecutionContext,
    config: ItemConfig,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
) -> dict:
    """Ensures page assets are downloaded and returns page storage context."""
    service = scraper.get_service()
    api = client.get_client()

    try:
        item = api.get_scraped_item(config.item_id)
        if not item:
            raise Exception(f"Scraped item {config.item_id} not found")

        page_url = item.get("sourcePageUrl") or item.get("productLink") or config.url
        store_slug = item.get("storeSlug") or config.store_slug
        ensured_item = api.ensure_source_page(config.item_id, page_url, store_slug)
        if not ensured_item:
            raise Exception(f"Failed to ensure source page for item {config.item_id}")

        page_id = ensured_item.get("sourcePageId")
        ensured_page_url = ensured_item.get("sourcePageUrl") or page_url
        if not page_id:
            raise Exception(f"Missing sourcePageId for item {config.item_id}")

        storage_path = service.download_assets(int(page_id), ensured_page_url)
        context.add_output_metadata(
            {
                "path": storage_path,
                "url": MetadataValue.url(ensured_page_url),
                "page_id": int(page_id),
                "origin_item_id": int(ensured_item["id"]),
            }
        )
        return {
            "storage_path": storage_path,
            "url": ensured_page_url,
            "page_id": int(page_id),
            "origin_item_id": int(ensured_item["id"]),
            "store_slug": ensured_item.get("storeSlug") or store_slug,
        }
    except Exception as e:
        context.log.error(f"Download failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise


@asset
def scraped_metadata(
    context: AssetExecutionContext,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
    downloaded_assets: dict,
) -> RawScrapedData:
    """Reads downloaded HTML and extracts lightweight metadata."""
    service = scraper.get_service()
    api = client.get_client()
    storage_path = downloaded_assets["storage_path"]
    page_url = downloaded_assets["url"]
    store_slug = downloaded_assets["store_slug"]
    origin_item_id = int(downloaded_assets["origin_item_id"])

    try:
        context.log.info(f"Extracting metadata from {storage_path}")
        meta_dict = service.extract_metadata(storage_path, page_url)
        raw_data = service.consolidate(meta_dict, brand_name_override=store_slug)
        context.add_output_metadata({"product_name": raw_data.name or "unknown"})
        return raw_data
    except Exception as e:
        context.log.error(f"Metadata extraction failed: {e}")
        api.report_error(origin_item_id, str(e), is_fatal=False)
        raise


@asset
def ocr_extraction(
    context: AssetExecutionContext,
    scraper: ScraperServiceResource,
    storage: StorageResource,
    client: AgentClientResource,
    scraped_metadata: RawScrapedData,
    downloaded_assets: dict,
) -> str:
    """Runs multimodal raw extraction over top-ranked page images."""
    store = storage.get_storage()
    service = scraper.get_service()
    api = client.get_client()
    origin_item_id = int(downloaded_assets["origin_item_id"])
    page_url = downloaded_assets["url"]

    bucket, _ = downloaded_assets["storage_path"].split("/", 1)
    try:
        candidates: list[dict] = []
        image_paths: list[str] = []
        candidates_key = "candidates.json"
        site_data: dict | None = None
        catalog_context: dict | None = None

        if store.exists(bucket, "site_data.json"):
            site_data = json.loads(store.download(bucket, "site_data.json"))
        if store.exists(bucket, "catalog_context.json"):
            catalog_context = json.loads(store.download(bucket, "catalog_context.json"))

        if not store.exists(bucket, candidates_key):
            candidates = service.materialize_candidates(bucket, page_url)
        if not candidates and store.exists(bucket, candidates_key):
            candidates = json.loads(store.download(bucket, candidates_key))
        if candidates:
            image_paths = _select_images_for_ocr(
                candidates,
                bucket,
                product_name=scraped_metadata.name or "",
                page_url=page_url,
            )
        extraction_mode = "multimodal"
        fallback_reason = ""
        if not image_paths:
            extraction_mode = "text_only"
            fallback_reason = (
                "no_candidates_available" if not candidates else "selection_empty"
            )
            context.log.warning(
                "OCR running in text-only mode: "
                f"{fallback_reason} for item {origin_item_id}"
            )
        sequence_context = _build_image_sequence_context(candidates, image_paths)
        llm_description = (
            (scraped_metadata.description or "")
            + sequence_context
            + _build_json_context_block("SITE_DATA", site_data)
            + _build_json_context_block("CATALOG_CONTEXT", catalog_context)
        )

        raw_text = run_raw_extraction(
            name=scraped_metadata.name or page_url,
            description=llm_description,
            image_paths=image_paths,
        )

        context.add_output_metadata(
            {
                "extraction_mode": extraction_mode,
                "fallback_reason": fallback_reason,
                "candidates_available": len(candidates),
                "images_used": len(image_paths),
                "images_sent": image_paths,
                "text_preview": MetadataValue.md(
                    (raw_text[:500] + "...") if raw_text else ""
                ),
            }
        )
        return raw_text
    except Exception as e:
        context.log.error(f"OCR extraction failed: {e}")
        api.report_error(origin_item_id, str(e), is_fatal=False)
        raise


@asset
def product_analysis(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    ocr_extraction: str,
) -> dict:
    """Converts raw text into structured list of product analyses."""
    api = client.get_client()
    try:
        result = run_structured_extraction(ocr_extraction)
        payload = result.model_dump(by_alias=True)

        expected_variant_signals = _extract_expected_variant_signals(ocr_extraction)
        expected_variant_count = len(expected_variant_signals)
        structured_variant_count = _count_structured_variant_signals(payload)
        reconciliation_retry_used = False
        catalog_guard_retry_used = False
        catalog_invalid_flavors = 0

        if (
            expected_variant_count >= 2
            and structured_variant_count < expected_variant_count
        ):
            context.log.warning(
                "Structured extraction under-detected variants "
                f"({structured_variant_count}/{expected_variant_count}). Retrying with reconciliation prompt."
            )
            reconciled = run_structured_extraction(
                ocr_extraction,
                prompt=_build_reconciliation_prompt(expected_variant_count),
            )
            reconciled_payload = reconciled.model_dump(by_alias=True)
            reconciled_variant_count = _count_structured_variant_signals(
                reconciled_payload
            )
            if reconciled_variant_count >= structured_variant_count:
                payload = reconciled_payload
                structured_variant_count = reconciled_variant_count
                reconciliation_retry_used = True

        catalog_context = _extract_context_block(ocr_extraction, "CATALOG_CONTEXT")
        allowed_flavors = _extract_allowed_flavors_from_catalog(catalog_context)
        catalog_invalid_flavors = _count_invalid_catalog_flavors(
            payload, allowed_flavors
        )
        if allowed_flavors and catalog_invalid_flavors > 0:
            context.log.warning(
                "Structured extraction returned flavors outside catalog "
                f"({catalog_invalid_flavors} invalid). Retrying with catalog guard."
            )
            guarded = run_structured_extraction(
                ocr_extraction,
                prompt=_build_catalog_guard_prompt(allowed_flavors),
            )
            guarded_payload = guarded.model_dump(by_alias=True)
            guarded_invalid = _count_invalid_catalog_flavors(
                guarded_payload, allowed_flavors
            )
            guarded_variant_count = _count_structured_variant_signals(guarded_payload)
            if guarded_invalid < catalog_invalid_flavors or (
                guarded_invalid == catalog_invalid_flavors
                and guarded_variant_count >= structured_variant_count
            ):
                payload = guarded_payload
                structured_variant_count = guarded_variant_count
                catalog_invalid_flavors = guarded_invalid
                catalog_guard_retry_used = True

        context.add_output_metadata(
            {
                "items_detected": len(payload.get("items", [])),
                "variants_detected_raw": expected_variant_count,
                "variants_detected_structured": structured_variant_count,
                "reconciliation_retry_used": reconciliation_retry_used,
                "catalog_guard_retry_used": catalog_guard_retry_used,
                "catalog_invalid_flavors": catalog_invalid_flavors,
            }
        )
        return payload
    except Exception as e:
        context.log.error(f"Structured analysis failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise


@asset
def upload_to_api(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    product_analysis: dict,
    scraped_metadata: RawScrapedData,
) -> list[dict]:
    """Creates one product per analyzed item and links generated scraped items."""
    api = client.get_client()
    try:
        origin_item = api.get_scraped_item(config.item_id)
        if not origin_item:
            raise Exception(f"Scraped item {config.item_id} not found")

        origin_page_url = (
            origin_item.get("sourcePageUrl")
            or origin_item.get("productLink")
            or config.url
        )
        origin_store_slug = origin_item.get("storeSlug") or config.store_slug
        ensured_origin = api.ensure_source_page(
            config.item_id, origin_page_url, origin_store_slug
        )
        if not ensured_origin:
            raise Exception(f"Failed to ensure source page for item {config.item_id}")

        page_url = ensured_origin.get("sourcePageUrl") or origin_page_url

        items = product_analysis.get("items") or []
        if not items:
            items = [
                {
                    "name": scraped_metadata.name
                    or origin_item.get("name")
                    or "Unknown Product"
                }
            ]

        results: list[dict] = []
        created_count = 0
        for idx, analysis_data in enumerate(items):
            if idx == 0:
                scraped_item = (
                    api.update_scraped_item_data(
                        item_id=int(ensured_origin["id"]),
                        name=analysis_data.get("name"),
                        source_page_url=page_url,
                        store_slug=origin_store_slug,
                    )
                    or ensured_origin
                )
            else:
                base_name = (
                    analysis_data.get("name") or scraped_metadata.name or "product"
                )
                variant_name = analysis_data.get("variant_name") or f"v{idx + 1}"
                origin_external_id = str(ensured_origin.get("externalId") or "")
                ext_id = f"{origin_external_id}::v{idx + 1}-{_slugify(base_name)}-{_slugify(variant_name)}"[
                    :100
                ]
                scraped_item = api.upsert_scraped_item_variant(
                    origin_item_id=int(ensured_origin["id"]),
                    external_id=ext_id,
                    name=base_name,
                    page_url=page_url,
                    store_slug=origin_store_slug,
                    price=(
                        _to_float(origin_item.get("price"), default=0.0)
                        if origin_item.get("price") is not None
                        else None
                    ),
                    stock_status=origin_item.get("stockStatus"),
                )
                if not scraped_item:
                    raise Exception("Failed to upsert scraped item variant")
                created_count += 1

            # Idempotency guard: skip only when LINKED item has a valid ProductStore.
            status_value = str(scraped_item.get("status") or "").lower()
            product_store_id = scraped_item.get("productStoreId")
            if status_value == "linked" and product_store_id:
                context.log.info(
                    f"Skipping already linked item {scraped_item['id']} ({scraped_item.get('externalId')})"
                )
                linked_product_id = scraped_item.get("linkedProductId")
                results.append(
                    {
                        "product": {"id": linked_product_id},
                        "errors": [],
                        "skipped": True,
                    }
                )
                continue
            if status_value == "linked":
                context.log.warning(
                    f"Item {scraped_item['id']} marked LINKED without product_store; reprocessing."
                )

            tags_hierarchy = analysis_data.get("tags_hierarchy") or []
            payload = {
                "name": analysis_data.get("name")
                or scraped_metadata.name
                or "Unknown Product",
                "brandName": scraped_metadata.brand_name or "Unknown Brand",
                "weight": _to_int(analysis_data.get("weight_grams")),
                "ean": scraped_metadata.ean,
                "description": scraped_metadata.description,
                "packaging": analysis_data.get("packaging") or "CONTAINER",
                "originScrapedItemId": int(scraped_item["id"]),
                "stores": [
                    {
                        "storeName": origin_store_slug,
                        "productLink": page_url,
                        "price": _to_float(
                            scraped_metadata.price or origin_item.get("price") or 0.0
                        ),
                        "externalId": scraped_item.get("externalId"),
                        "stockStatus": _to_graphql_stock_status(
                            scraped_metadata.stock_status
                            or origin_item.get("stockStatus")
                        ),
                        "affiliateLink": "",
                    }
                ],
                "nutrition": _build_nutrition_payload(analysis_data),
                "categoryPath": analysis_data.get("category_hierarchy") or [],
                "tagPaths": [{"path": path} for path in tags_hierarchy if path],
                "tags": [],
                "isCombo": bool(analysis_data.get("is_combo")),
                "components": [
                    {
                        "name": c.get("name"),
                        "quantity": _to_int(c.get("quantity"), default=1),
                        "weightHint": c.get("weight_hint"),
                        "packagingHint": c.get("packaging_hint"),
                    }
                    for c in (analysis_data.get("components") or [])
                    if c.get("name")
                ],
                "nutrientClaims": analysis_data.get("nutrient_claims") or [],
                "isPublished": False,
            }

            context.log.info(
                f"Uploading product {idx + 1}/{len(items)} with origin item {scraped_item['id']}"
            )
            result = api.create_product(payload)
            results.append(result or {})

        context.add_output_metadata(
            {
                "items_uploaded": len(results),
                "additional_scraped_items_created": created_count,
                "page_id": ensured_origin.get("sourcePageId"),
            }
        )
        return results
    except Exception as e:
        context.log.error(f"Upload failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise
