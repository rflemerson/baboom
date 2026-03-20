"""Service for downloading page assets and extracting metadata for agents pipeline."""

from __future__ import annotations

import io
import json
import logging
import os
import statistics
import time
from datetime import UTC, datetime
from urllib.parse import urljoin

import extruct
import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image, ImageFilter
from w3lib.html import get_base_url

from ..schemas.product import RawScrapedData
from ..storage import get_storage

logger = logging.getLogger(__name__)

OG_IMAGE_PROPERTY = "og:image"
JSON_CONTENT_TYPE = "application/json"
HTML_PARSER = "html.parser"
DEFAULT_IMAGE_CONTENT_TYPE = "image/jpeg"
JPEG_CONTENT_TYPE = "image/jpeg"


def _safe_int(value) -> int | None:
    """Parse optional integer-like values from HTML attributes."""
    try:
        if value is None or value == "":
            return None
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _infer_source_type(src: str) -> str:
    """Infer image source from raw src string."""
    lowered = src.lower()
    if OG_IMAGE_PROPERTY in lowered:
        return OG_IMAGE_PROPERTY
    if "ld+json" in lowered:
        return "jsonld"
    return "img"


class ScraperService:
    """Service to download and process web assets."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        }
        self.storage = get_storage()
        self.http_retries = max(1, int(os.getenv("AGENTS_HTTP_RETRIES", "3")))
        self.http_backoff = float(os.getenv("AGENTS_HTTP_RETRY_BACKOFF", "0.6"))

    def _request_get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> requests.Response:
        """GET with retries for transient failures."""
        last_response: requests.Response | None = None
        for attempt in range(1, self.http_retries + 1):
            response = requests.get(
                url,
                headers=headers or self.headers,
                timeout=timeout,
            )
            last_response = response
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            if attempt < self.http_retries:
                time.sleep(self.http_backoff * attempt)
        if last_response is None:
            raise RuntimeError(f"HTTP request failed for {url}")
        return last_response

    def download_assets(
        self,
        item_id: int,
        url: str,
        html_content: str | None = None,
    ) -> str:
        """Downloads page HTML and lightweight image manifest to storage."""
        bucket = str(item_id)

        try:
            if not html_content:
                html_content = self._download_html(url)

            html_key = "source.html"
            self.storage.upload(
                bucket,
                html_key,
                html_content.encode("utf-8"),
                content_type="text/html",
            )

            manifest = self._build_image_manifest(html_content, url)
            site_data = self._extract_site_data(html_content, url)

            self.storage.upload(
                bucket,
                "image_manifest.json",
                json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
                content_type=JSON_CONTENT_TYPE,
            )
            self.storage.upload(
                bucket,
                "site_data.json",
                json.dumps(site_data, indent=2, ensure_ascii=False).encode("utf-8"),
                content_type=JSON_CONTENT_TYPE,
            )

            images_count = len(manifest.get("images", []))
            logger.info(
                f"Indexed {images_count} images for {item_id} (manifest-only mode)",
            )
            return f"{bucket}/{html_key}"

        except Exception as e:
            logger.error(f"Error downloading assets for {url}: {e}")
            raise

    def _download_html(self, url: str) -> str:
        logger.info(f"Downloading HTML from {url}")
        response = self._request_get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def _build_image_manifest(self, html_content: str, base_url: str) -> dict:
        """Extract image links/metadata quickly without downloading bytes."""
        soup = BeautifulSoup(html_content, HTML_PARSER)
        sources = self._extract_image_sources(soup)

        manifest: list[dict] = []
        seen_urls: set[str] = set()
        for index, (src, tag) in enumerate(sources):
            if not src or not isinstance(src, str):
                continue
            img_url = urljoin(base_url, src)
            if img_url in seen_urls:
                continue
            seen_urls.add(img_url)
            declared_width = _safe_int(tag.get("width"))
            declared_height = _safe_int(tag.get("height"))
            manifest.append(
                {
                    "position": index,
                    "url": img_url,
                    "source": _infer_source_type(src),
                    "declared_dimensions": [declared_width, declared_height],
                    "metadata": {
                        "alt": self._get_attr(tag, "alt"),
                        "id": self._get_attr(tag, "id"),
                        "class": self._get_attr(tag, "class"),
                        "title": self._get_attr(tag, "title"),
                    },
                },
            )
        return {
            "page_url": base_url,
            "generated_at": datetime.now(UTC).isoformat(),
            "images": manifest,
        }

    def _extract_site_data(self, html_content: str, page_url: str) -> dict:
        """Extract structured page data for LLM context blocks."""
        try:
            base_url = get_base_url(html_content, page_url)
            extracted = extruct.extract(html_content, base_url=base_url)
        except Exception as e:
            logger.warning(
                f"Failed to extract site_data via extruct for {page_url}: {e}",
            )
            extracted = {}
        return {
            "page_url": page_url,
            "generated_at": datetime.now(UTC).isoformat(),
            "extracted": extracted,
        }

    def materialize_candidates(self, bucket: str, page_url: str) -> list[dict]:
        """Dagster-side heavy step: download image bytes and compute CV scores."""
        try:
            manifest_payload = json.loads(
                self.storage.download(bucket, "image_manifest.json"),
            )
        except Exception as e:
            logger.warning(f"No image manifest for bucket {bucket}: {e}")
            return []

        manifest = (
            manifest_payload.get("images")
            if isinstance(manifest_payload, dict)
            else manifest_payload
        )
        if not isinstance(manifest, list):
            return []

        candidates: list[dict] = []
        seen_hashes: set[str] = set()

        for item in manifest:
            if not isinstance(item, dict):
                continue
            img_url = str(item.get("url") or "")
            if not img_url:
                continue
            tag = self._tag_from_manifest_item(item)
            position = int(item.get("position") or 0)
            candidate = self._process_single_candidate(
                position,
                img_url,
                tag,
                bucket,
                seen_hashes,
            )
            if candidate:
                candidates.append(candidate)

        candidates.sort(key=lambda x: int(str(x.get("score", 0))), reverse=True)
        self.storage.upload(
            bucket,
            "candidates.json",
            json.dumps(candidates, indent=2).encode("utf-8"),
            content_type=JSON_CONTENT_TYPE,
        )
        logger.info(
            f"Materialized {len(candidates)} OCR candidates for bucket {bucket} ({page_url})",
        )
        return candidates

    def _tag_from_manifest_item(self, item: dict) -> Tag:
        """Create synthetic img Tag from manifest metadata for keyword scoring."""
        soup = BeautifulSoup("", HTML_PARSER)
        tag = soup.new_tag("img")
        metadata = item.get("metadata") or {}
        for key in ("alt", "title", "id", "class"):
            value = metadata.get(key)
            if value:
                tag[key] = str(value)
        return tag

    def _process_images(
        self,
        html_content: str,
        base_url: str,
        bucket: str,
    ) -> list[dict]:
        """Extract and score images from HTML."""
        soup = BeautifulSoup(html_content, HTML_PARSER)
        sources = self._extract_image_sources(soup)

        candidates = []
        seen_urls = set()
        seen_hashes: set[str] = set()

        for i, (src, tag) in enumerate(sources):
            if not src or not isinstance(src, str):
                continue

            img_url = urljoin(base_url, src)
            if img_url in seen_urls:
                continue
            seen_urls.add(img_url)

            candidate = self._process_single_candidate(
                i,
                img_url,
                tag,
                bucket,
                seen_hashes,
            )
            if candidate:
                candidates.append(candidate)

        candidates.sort(key=lambda x: int(str(x["score"])), reverse=True)
        return candidates

    def _extract_image_sources(self, soup: BeautifulSoup) -> list[tuple[str, Tag]]:
        sources = []
        for img in soup.find_all("img"):
            for attr in ["src", "data-src", "data-zoom", "data-lazy", "data-original"]:
                src = img.get(attr)
                if src and isinstance(src, str):
                    sources.append((src, img))
                    break

        for meta in soup.find_all("meta", property=OG_IMAGE_PROPERTY):
            src = meta.get("content")
            if src and isinstance(src, str):
                sources.append((src, meta))

        self._extract_json_ld_images(soup, sources)
        return sources

    def _extract_json_ld_images(self, soup: BeautifulSoup, sources: list) -> None:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                for img_url in self._json_ld_image_urls(script):
                    sources.append((img_url, script))
            except Exception as e:
                logger.debug(f"JSON-LD parsing failed: {e}")

    def _json_ld_image_urls(self, script: Tag) -> list[str]:
        """Extract image URLs from one JSON-LD script block."""
        if not script.string:
            return []
        data = json.loads(script.string)
        if not isinstance(data, dict) or "image" not in data:
            return []
        images = data["image"]
        if isinstance(images, str):
            return [images]
        if isinstance(images, list):
            return [str(img_url) for img_url in images]
        return []

    def _process_single_candidate(
        self,
        index: int,
        img_url: str,
        tag: Tag,
        bucket: str,
        seen_hashes: set,
    ) -> dict | None:
        try:
            img_resp = self._request_get(img_url, timeout=10)
            if img_resp.status_code != 200:
                return None

            content = img_resp.content
            if not self._check_hash(content, img_url, seen_hashes):
                return None

            ext = urljoin(img_url, "").split("?")[0].split(".")[-1].lower()
            if ext == "svg":
                return None
            if not ext or len(ext) > 5:
                ext = "jpg"

            score, width, height, nutrition_signal, cv_table_score = (
                self._calculate_image_score(tag, img_url, content)
            )

            if width < 200 or height < 200:
                return None

            image_key = f"images/image_{index}.{ext}"
            content_type_map = {
                "jpg": JPEG_CONTENT_TYPE,
                "jpeg": JPEG_CONTENT_TYPE,
                "png": "image/png",
                "webp": "image/webp",
            }
            self.storage.upload(
                bucket,
                image_key,
                content,
                content_type=content_type_map.get(ext, DEFAULT_IMAGE_CONTENT_TYPE),
            )

            return {
                "file": image_key,
                "url": img_url,
                "score": score,
                "nutrition_signal": nutrition_signal,
                "cv_table_score": cv_table_score,
                "dimensions": [width, height],
                "metadata": {
                    "alt": self._get_attr(tag, "alt"),
                    "id": self._get_attr(tag, "id"),
                    "class": self._get_attr(tag, "class"),
                    "title": self._get_attr(tag, "title"),
                },
            }
        except Exception as e:
            logger.debug(f"Failed to process image {img_url}: {e}")
            return None

    def _check_hash(self, content: bytes, img_url: str, seen_hashes: set) -> bool:
        try:
            p_hash = self._compute_phash(content)
            if p_hash in seen_hashes:
                logger.debug(f"Skipping duplicate image (hash match): {img_url}")
                return False
            seen_hashes.add(p_hash)
            return True
        except Exception as e:
            logger.debug(f"Hash computation failed for {img_url}: {e}")
            return True

    def _get_attr(self, tag: Tag, name: str) -> str:
        val = tag.get(name, "")
        if isinstance(val, list):
            return " ".join(val)
        return str(val) if val else ""

    def _compute_phash(self, content: bytes) -> str:
        img = (
            Image.open(io.BytesIO(content))
            .convert("L")
            .resize((8, 8), Image.Resampling.LANCZOS)
        )
        pixels = list(img.getdata())
        avg = sum(pixels) / 64
        bits = "".join("1" if p > avg else "0" for p in pixels)
        return hex(int(bits, 2))[2:].zfill(16)

    def _calculate_image_score(
        self,
        img_tag: Tag,
        img_url: str,
        content: bytes,
    ) -> tuple[int, int, int, int, float]:
        score = 0
        keyword_score, nutrition_signal = self._score_by_keywords(img_tag, img_url)
        score += keyword_score
        width, height = 0, 0
        cv_table_score = 0.0
        try:
            with Image.open(io.BytesIO(content)) as im:
                width, height = im.size
                score += self._score_by_dimensions(width, height)
            cv_table_score = self._estimate_table_structure_score(content)
            score += int(cv_table_score * 40)
        except Exception as e:
            logger.debug(f"Could not check dimensions for {img_url}: {e}")

        return score, width, height, nutrition_signal, cv_table_score

    def _estimate_table_structure_score(self, content: bytes) -> float:
        img = Image.open(io.BytesIO(content)).convert("L")
        img.thumbnail((900, 900))
        width, height = img.size
        if width < 80 or height < 80:
            return 0.0

        edges = img.filter(ImageFilter.FIND_EDGES)
        edge_values = list(edges.getdata())
        threshold = int(statistics.mean(edge_values) + statistics.pstdev(edge_values))
        bw = edges.point(lambda p: 255 if p >= threshold else 0, mode="1")
        pixels = bw.load()

        min_h_run = max(30, int(width * 0.40))
        min_v_run = max(30, int(height * 0.40))

        row_is_line = self._detect_horizontal_lines(pixels, width, height, min_h_run)
        col_is_line = self._detect_vertical_lines(pixels, width, height, min_v_run)

        row_count = sum(row_is_line)
        col_count = sum(col_is_line)
        if row_count == 0 and col_count == 0:
            return 0.0

        intersections = 0
        for y in range(height):
            if not row_is_line[y]:
                continue
            for x in range(width):
                if col_is_line[x] and pixels[x, y] == 255:
                    intersections += 1

        h_ratio = row_count / height
        v_ratio = col_count / width
        grid_density = intersections / max(1, row_count * col_count)

        h_quality = max(0.0, 1.0 - abs(h_ratio - 0.10) / 0.10)
        v_quality = max(0.0, 1.0 - abs(v_ratio - 0.10) / 0.10)
        grid_quality = min(1.0, grid_density * 20.0)
        score = (0.35 * h_quality) + (0.35 * v_quality) + (0.30 * grid_quality)
        return float(min(1.0, max(0.0, score)))

    def _detect_horizontal_lines(
        self,
        pixels,
        width: int,
        height: int,
        min_h_run: int,
    ) -> list[bool]:
        row_is_line = [False] * height
        for y in range(height):
            longest = 0
            current = 0
            ink_count = 0
            for x in range(width):
                if pixels[x, y] == 255:
                    ink_count += 1
                    current += 1
                    longest = max(longest, current)
                else:
                    current = 0
            ink_ratio = ink_count / width
            row_is_line[y] = longest >= min_h_run and 0.01 <= ink_ratio <= 0.95
        return row_is_line

    def _detect_vertical_lines(
        self,
        pixels,
        width: int,
        height: int,
        min_v_run: int,
    ) -> list[bool]:
        col_is_line = [False] * width
        for x in range(width):
            longest = 0
            current = 0
            ink_count = 0
            for y in range(height):
                if pixels[x, y] == 255:
                    ink_count += 1
                    current += 1
                    longest = max(longest, current)
                else:
                    current = 0
            ink_ratio = ink_count / height
            col_is_line[x] = longest >= min_v_run and 0.01 <= ink_ratio <= 0.95
        return col_is_line

    def _score_by_keywords(self, img_tag: Tag, img_url: str) -> tuple[int, int]:
        score = 0
        alt_text = self._get_attr(img_tag, "alt").lower()
        title_text = self._get_attr(img_tag, "title").lower()
        img_id = self._get_attr(img_tag, "id").lower()
        img_class = self._get_attr(img_tag, "class").lower()
        src_lower = img_url.lower()

        nutrition_keywords = [
            "tabela",
            "nutricional",
            "nutrition",
            "facts",
            "label",
            "tabela_nutricional",
            "informacao",
            "ingredientes",
            "composition",
            "composicao",
            "valor",
            "energetico",
        ]
        nutrition_signal = 0
        if any(kw in alt_text for kw in nutrition_keywords) and (
            any(k in alt_text for k in ["info", "tabela", "label", "rotulo", "facts"])
        ):
            score += 60
            nutrition_signal += 3

        if any(
            kw in img_id or kw in img_class
            for kw in ["nutri", "tabela", "label", "rotulo"]
        ):
            score += 40
            nutrition_signal += 2

        keywords = [
            "tabela",
            "nutricional",
            "nutrition",
            "fatos",
            "facts",
            "info",
            "tab",
            "ingredientes",
            "ingrediente",
        ]
        for kw in keywords:
            if kw in alt_text:
                score += 10
                nutrition_signal += 1
            if kw in title_text:
                score += 5
                nutrition_signal += 1
            if kw in src_lower:
                score += 5
                nutrition_signal += 1
            if kw in img_class:
                score += 5
                nutrition_signal += 1
        return score, nutrition_signal

    def _score_by_dimensions(self, width: int, height: int) -> int:
        score = 0
        if width < 100 or height < 100:
            score -= 50
        elif width > 300 and height > 300:
            score += 10

        aspect_ratio = width / height if height > 0 else 1
        if 0.5 <= aspect_ratio <= 1.2:
            score += 15
        if aspect_ratio > 3.0 or aspect_ratio < 0.2:
            score -= 40
        return score

    def extract_metadata(self, html_storage_path: str, url: str) -> dict:
        """Extracts metadata using extruct from HTML in storage."""
        bucket, key = html_storage_path.split("/", 1)
        try:
            html_content = self.storage.download(bucket, key).decode("utf-8")
            base_url = get_base_url(html_content, url)
            data = extruct.extract(html_content, base_url=base_url)

            try:
                soup = BeautifulSoup(html_content, "html.parser")
                nutrition_text = self._extract_html_nutrition(soup)
                if nutrition_text:
                    data["custom_nutrition_text"] = nutrition_text
            except Exception as e:
                logger.warning(f"Failed to extract custom HTML nutrition: {e}")

            self.storage.upload(
                bucket,
                "data.json",
                json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"),
                content_type="application/json",
            )

            return data
        except Exception as e:
            logger.error(f"Error extracting metadata from {html_storage_path}: {e}")
            raise

    def _extract_html_nutrition(self, soup: BeautifulSoup) -> str:
        try:
            table = soup.select_one(".nutrition-info-table")
            if table:
                lines = []
                for row in table.select("tr"):
                    cols = [c.get_text(strip=True) for c in row.select("th, td")]
                    lines.append(" | ".join(cols))
                return "\n".join(lines)
        except Exception as e:
            logger.debug(f"HTML table extraction failed: {e}")
        return ""

    def consolidate(
        self,
        metadata: dict,
        brand_name_override: str | None = None,
        price: float | None = None,
        stock_status: str | None = "A",
    ) -> RawScrapedData:
        """Consolidates raw extracted metadata into a simple data structure."""
        product_info = self._extract_product_info(metadata)

        name = (
            product_info.get("name")
            or metadata.get("opengraph", [{}])[0].get("og:title")
            or "Unknown Product"
        )
        brand_name = brand_name_override or self._extract_brand(product_info)

        description = (
            product_info.get("description")
            or metadata.get("opengraph", [{}])[0].get("og:description")
            or ""
        )

        if metadata.get("custom_nutrition_text"):
            description += f"\n\n--- NUTRITION TABLE RAW TEXT ---\n{metadata['custom_nutrition_text']}\n--------------------------------"

        image_url = self._extract_image_url(product_info, metadata)
        ean = (
            product_info.get("gtin")
            or product_info.get("gtin13")
            or product_info.get("sku")
        )
        category = product_info.get("category")

        return RawScrapedData(
            name=name,
            brand_name=brand_name,
            ean=ean,
            description=description,
            image_url=image_url,
            price=price,
            stock_status=stock_status,
            category=category,
        )

    def _extract_product_info(self, metadata: dict) -> dict:
        json_ld = metadata.get("json-ld", [])
        for item in json_ld:
            if item.get("@type") == "Product":
                return item
        return {}

    def _extract_brand(self, product_info: dict) -> str:
        brand_data = product_info.get("brand", {})
        if isinstance(brand_data, dict):
            return brand_data.get("name", "Unknown Brand")
        if isinstance(brand_data, str):
            return brand_data
        return "Unknown Brand"

    def _extract_image_url(self, product_info: dict, metadata: dict) -> str | None:
        image_url = product_info.get("image") or metadata.get("opengraph", [{}])[0].get(
            "og:image",
        )
        if isinstance(image_url, list):
            return image_url[0] if image_url else None
        return image_url
