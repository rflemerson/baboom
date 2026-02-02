"""Service for scraping and consolidating product data."""

from __future__ import annotations

import io
import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import extruct
import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image
from w3lib.html import get_base_url

from ..schemas.product import RawScrapedData
from ..storage import get_storage

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ScraperService:
    """Service to download and process web assets."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.storage = get_storage()

    def download_assets(self, item_id: int, url: str) -> str:
        """
        Downloads HTML and images to the storage backend.

        Returns the storage path/key to the saved HTML file.
        """
        bucket = str(item_id)

        try:
            html_content = self._download_html(url)
            html_key = "source.html"
            self.storage.upload(
                bucket, html_key, html_content.encode("utf-8"), content_type="text/html"
            )

            candidates = self._process_images(html_content, url, bucket)

            manifest_key = "candidates.json"
            self.storage.upload(
                bucket,
                manifest_key,
                json.dumps(candidates, indent=2).encode("utf-8"),
                content_type="application/json",
            )

            logger.info(
                f"Downloaded {len(candidates)} images for {item_id}. Top score: {candidates[0]['score'] if candidates else 0}"
            )
            return f"{bucket}/{html_key}"

        except Exception as e:
            logger.error(f"Error downloading assets for {url}: {e}")
            raise

    def _download_html(self, url: str) -> str:
        logger.info(f"Downloading HTML from {url}")
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.text

    def _process_images(
        self, html_content: str, base_url: str, bucket: str
    ) -> list[dict]:
        """Extract and score images from HTML."""
        soup = BeautifulSoup(html_content, "html.parser")
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
                i, img_url, tag, bucket, seen_hashes
            )
            if candidate:
                candidates.append(candidate)

        # Sort candidates by score descending
        candidates.sort(key=lambda x: int(str(x["score"])), reverse=True)
        return candidates

    def _extract_image_sources(self, soup: BeautifulSoup) -> list[tuple[str, Tag]]:
        sources = []
        for img in soup.find_all("img"):
            # Check multiple src-like attributes used by lazy loaders
            for attr in ["src", "data-src", "data-zoom", "data-lazy", "data-original"]:
                src = img.get(attr)
                if src and isinstance(src, str):
                    sources.append((src, img))
                    break  # Only take one per img tag

        # OpenGraph images
        for meta in soup.find_all("meta", property="og:image"):
            src = meta.get("content")
            if src and isinstance(src, str):
                sources.append((src, meta))

        # JSON-LD or Script embedded images
        self._extract_json_ld_images(soup, sources)

        return sources

    def _extract_json_ld_images(self, soup: BeautifulSoup, sources: list) -> None:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if not script.string:
                    continue
                data = json.loads(script.string)
                if isinstance(data, dict) and "image" in data:
                    imgs = data["image"]
                    if isinstance(imgs, str):
                        sources.append((imgs, script))
                    elif isinstance(imgs, list):
                        for img_url in imgs:
                            sources.append((img_url, script))
            except Exception as e:
                logger.debug(f"JSON-LD parsing failed: {e}")

    def _process_single_candidate(
        self, index: int, img_url: str, tag: Tag, bucket: str, seen_hashes: set
    ) -> dict | None:
        try:
            img_resp = requests.get(img_url, headers=self.headers, timeout=10)
            if img_resp.status_code != 200:
                return None

            content = img_resp.content

            # De-duplication check
            if not self._check_hash(content, img_url, seen_hashes):
                return None

            # Extension check
            ext = urljoin(img_url, "").split("?")[0].split(".")[-1].lower()
            if ext == "svg":
                return None
            if not ext or len(ext) > 5:
                ext = "jpg"

            score, width, height = self._calculate_image_score(tag, img_url, content)

            # Skip small images
            if width < 200 or height < 200:
                return None

            image_key = f"images/image_{index}.{ext}"
            self.storage.upload(bucket, image_key, content, content_type="image/jpeg")

            return {
                "file": image_key,
                "url": img_url,
                "score": score,
                "dimensions": [width, height],
                "metadata": {
                    "alt": self._get_attr(tag, "alt"),
                    "id": self._get_attr(tag, "id"),
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
        """Computes a simple 8x8 perceptual hash to identify visually similar images."""
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
        self, img_tag: Tag, img_url: str, content: bytes
    ) -> tuple[int, int, int]:
        """Calculate relevance score for an image."""
        score = 0
        score += self._score_by_keywords(img_tag, img_url)
        width, height = 0, 0
        try:
            with Image.open(io.BytesIO(content)) as im:
                width, height = im.size
                score += self._score_by_dimensions(width, height)
        except Exception as e:
            logger.debug(f"Could not check dimensions for {img_url}: {e}")

        return score, width, height

    def _score_by_keywords(self, img_tag: Tag, img_url: str) -> int:
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
        if any(kw in alt_text for kw in nutrition_keywords) and (
            any(k in alt_text for k in ["info", "tabela", "label", "rotulo", "facts"])
        ):
            score += 60

        if any(
            kw in img_id or kw in img_class
            for kw in ["nutri", "tabela", "label", "rotulo"]
        ):
            score += 40

        keywords = [
            "tabela",
            "nutricional",
            "nutrition",
            "fatos",
            "facts",
            "info",
            "tab",
            "ingredientes",
            "composição",
            "ingrediente",
        ]
        for kw in keywords:
            if kw in alt_text:
                score += 10
            if kw in title_text:
                score += 5
            if kw in src_lower:
                score += 5
            if kw in img_class:
                score += 5
        return score

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

            # Custom extraction for nutrition tables hidden in HTML
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
        """Extracts text from known nutrition table containers."""
        try:
            # Selector specific to Soldiers Nutrition / Vtex legacy
            table = soup.select_one(".nutrition-info-table")
            if table:
                # Basic text extraction, preserving some structure
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

        # Append custom extracted nutrition text
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
            "og:image"
        )
        if isinstance(image_url, list):
            return image_url[0] if image_url else None
        return image_url
