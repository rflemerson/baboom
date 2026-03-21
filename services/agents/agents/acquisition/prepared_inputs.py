"""Prepare deterministic extraction inputs from persisted source artifacts."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Protocol

from ..contracts.acquisition import PreparedExtractionInputs
from ..extraction.image_selection import select_images_for_ocr

if TYPE_CHECKING:
    from ..schemas.product import RawScrapedData


class AcquisitionStorage(Protocol):
    """Storage surface needed while preparing extraction inputs."""

    def exists(self, bucket: str, key: str) -> bool:
        """Return whether a persisted artifact exists."""

    def download(self, bucket: str, key: str) -> str:
        """Download one persisted text artifact."""


class CandidateService(Protocol):
    """Scraper-service surface needed while preparing extraction inputs."""

    def materialize_candidates(self, bucket: str, page_url: str) -> list[dict]:
        """Create or refresh OCR candidates for one persisted page bucket."""


def build_prepared_extraction_inputs(
    *,
    store: AcquisitionStorage,
    service: CandidateService,
    downloaded_assets: dict,
    scraped_metadata: RawScrapedData,
) -> PreparedExtractionInputs:
    """Build the deterministic handoff between acquisition and extraction."""
    bucket, _ = downloaded_assets["storage_path"].split("/", 1)
    page_url = downloaded_assets["url"]
    candidates, materialize_ms = load_candidates(store, service, bucket, page_url)
    image_paths = select_images_for_ocr(
        candidates,
        bucket,
        product_name=scraped_metadata.name or "",
        page_url=page_url,
    )
    extraction_mode, fallback_reason = resolve_extraction_mode(candidates, image_paths)
    return PreparedExtractionInputs(
        origin_item_id=int(downloaded_assets["origin_item_id"]),
        page_url=page_url,
        storage_path=downloaded_assets["storage_path"],
        bucket=bucket,
        scraper_context=load_scraper_context(downloaded_assets),
        site_data=load_site_data(store, bucket),
        candidates=candidates,
        image_paths=image_paths,
        extraction_mode=extraction_mode,
        fallback_reason=fallback_reason,
        materialize_ms=materialize_ms,
    )


def load_scraper_context(downloaded_assets: dict) -> dict | None:
    """Parse JSON scraper context when source page payload is available."""
    raw_scraper_context = downloaded_assets.get("source_page_raw_content")
    scraper_context_type = str(
        downloaded_assets.get("source_page_content_type") or "",
    ).upper()
    if not raw_scraper_context or scraper_context_type != "JSON":
        return None
    try:
        parsed_context = json.loads(raw_scraper_context)
    except json.JSONDecodeError:
        return None
    return parsed_context if isinstance(parsed_context, dict) else None


def load_site_data(store: AcquisitionStorage, bucket: str) -> dict | None:
    """Load persisted site data block when present."""
    if not store.exists(bucket, "site_data.json"):
        return None
    return json.loads(store.download(bucket, "site_data.json"))


def load_candidates(
    store: AcquisitionStorage,
    service: CandidateService,
    bucket: str,
    page_url: str,
) -> tuple[list[dict], float]:
    """Load or materialize OCR candidates for one page bucket."""
    candidates_key = "candidates.json"
    if store.exists(bucket, candidates_key):
        return json.loads(store.download(bucket, candidates_key)), 0.0

    materialize_started = time.perf_counter()
    candidates = service.materialize_candidates(bucket, page_url)
    materialize_ms = round((time.perf_counter() - materialize_started) * 1000, 2)
    return candidates, materialize_ms


def resolve_extraction_mode(
    candidates: list[dict],
    image_paths: list[str],
) -> tuple[str, str]:
    """Return extraction mode and fallback reason for OCR metadata."""
    if image_paths:
        return "multimodal", ""
    fallback_reason = "no_candidates_available" if not candidates else "selection_empty"
    return "text_only", fallback_reason
