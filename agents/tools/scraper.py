from __future__ import annotations

import io
import json
import logging
import os
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import extruct
import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image
from w3lib.html import get_base_url

from ..storage import get_storage

if TYPE_CHECKING:
    from ..schemas.product import RawScrapedData

logger = logging.getLogger(__name__)


class ScraperService:
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
            # 1. Download HTML
            html_content = self._download_html(url)
            html_key = "source.html"
            self.storage.upload(
                bucket, html_key, html_content.encode("utf-8"), content_type="text/html"
            )

            # 2. Process and download images
            candidates = self._process_images(html_content, url, bucket)

            # 3. Save Candidates Manifest
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
        soup = BeautifulSoup(html_content, "html.parser")
        images = soup.find_all("img")
        candidates = []

        def _get_attr(tag: Tag, name: str) -> str:
            val = tag.get(name, "")
            if isinstance(val, list):
                return " ".join(val)
            return str(val) if val else ""

        for i, img in enumerate(images):
            if not isinstance(img, Tag):
                continue

            src = img.get("src")
            if not src or not isinstance(src, str):
                continue

            img_url = urljoin(base_url, src)
            try:
                img_resp = requests.get(img_url, headers=self.headers, timeout=10)
                if img_resp.status_code != 200:
                    continue

                content = img_resp.content
                score, width, height = self._calculate_image_score(
                    img, img_url, content
                )

                # Determine extension and save
                ext = os.path.splitext(img_url)[1].split("?")[0]
                if not ext or len(ext) > 5:
                    ext = ".jpg"

                image_key = f"images/image_{i}{ext}"
                self.storage.upload(
                    bucket, image_key, content, content_type="image/jpeg"
                )

                candidates.append(
                    {
                        "file": image_key,
                        "url": img_url,
                        "score": score,
                        "dimensions": [width, height],
                        "metadata": {
                            "alt": _get_attr(img, "alt"),
                            "id": _get_attr(img, "id"),
                        },
                    }
                )
            except Exception as e:
                logger.debug(f"Failed to process image {img_url}: {e}")

        # Sort candidates by score descending
        candidates.sort(key=lambda x: int(str(x["score"])), reverse=True)
        return candidates

    def _calculate_image_score(
        self, img_tag: Tag, img_url: str, content: bytes
    ) -> tuple[int, int, int]:
        score = 0

        def _get_attr(name: str) -> str:
            val = img_tag.get(name, "")
            if isinstance(val, list):
                return " ".join(val)
            return str(val) if val else ""

        alt_text = _get_attr("alt").lower()
        title_text = _get_attr("title").lower()
        img_id = _get_attr("id").lower()
        img_class = _get_attr("class").lower()
        src_lower = img_url.lower()

        # High confidence matches
        if "tabela" in alt_text and "nutricional" in alt_text:
            score += 50
        if "nutrition" in alt_text and "facts" in alt_text:
            score += 50
        if "tabela" in img_id or "nutri" in img_id:
            score += 30

        # General keywords
        keywords = [
            "tabela",
            "nutricional",
            "nutrition",
            "fatos",
            "facts",
            "info",
            "tab",
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

        # Dimension Check
        width, height = 0, 0
        try:
            with Image.open(io.BytesIO(content)) as im:
                width, height = im.size
                if width < 100 or height < 100:
                    score -= 50
                elif width > 300 and height > 300:
                    score += 10
        except Exception as e:
            logger.debug(f"Could not check dimensions for {img_url}: {e}")

        return score, width, height

    def extract_metadata(self, html_storage_path: str, url: str) -> dict:
        """
        Extracts metadata using extruct from HTML in storage.
        """
        bucket, key = html_storage_path.split("/", 1)
        try:
            html_content = self.storage.download(bucket, key).decode("utf-8")
            base_url = get_base_url(html_content, url)
            data = extruct.extract(html_content, base_url=base_url)

            # Save to storage
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

    def consolidate(
        self,
        metadata: dict,
        brand_name_override: str | None = None,
        price: float | None = None,
        stock_status: str | None = "A",
    ) -> RawScrapedData:
        """
        Consolidates raw extracted metadata into a simple data structure.
        """
        from ..schemas.product import RawScrapedData

        product_info = self._extract_product_info(metadata)

        name = (
            product_info.get("name")
            or metadata.get("opengraph", [{}])[0].get("og:title")
            or "Unknown Product"
        )
        brand_name = brand_name_override or self._extract_brand(product_info)
        description = product_info.get("description") or metadata.get(
            "opengraph", [{}]
        )[0].get("og:description")
        image_url = self._extract_image_url(product_info, metadata)
        ean = (
            product_info.get("gtin")
            or product_info.get("gtin13")
            or product_info.get("sku")
        )

        return RawScrapedData(
            name=name,
            brand_name=brand_name,
            ean=ean,
            description=description,
            image_url=image_url,
            price=price,
            stock_status=stock_status,
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
