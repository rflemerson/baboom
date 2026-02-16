"""Tests for scraper helper logic used by asset pipeline."""

import json
from typing import cast
from unittest.mock import MagicMock, patch

from agents.tools.scraper import ScraperService
from bs4 import BeautifulSoup, Tag
from django.test import SimpleTestCase, TestCase


class TestScraperToolHelpers(SimpleTestCase):
    """Unit tests for local scoring/parsing helpers."""

    def setUp(self):
        """Create service with mocked storage backend."""
        with patch("agents.tools.scraper.get_storage") as mock_storage:
            mock_storage.return_value = object()
            self.service = ScraperService()

    def test_score_by_keywords_detects_nutrition_signals(self):
        """Assigns nutrition signal when attributes mention nutrition table."""
        soup = BeautifulSoup(
            '<img alt="Nutrition Facts" class="label-nutri" src="/img/facts.jpg" />',
            "html.parser",
        )
        tag = soup.find("img")
        self.assertIsNotNone(tag)
        tag = cast(Tag, tag)
        score, signal = self.service._score_by_keywords(tag, "https://x/facts.jpg")

        self.assertGreater(score, 0)
        self.assertGreater(signal, 0)

    def test_score_by_keywords_has_no_signal_for_generic_image(self):
        """Keeps zero nutrition signal for non-nutrition image metadata."""
        soup = BeautifulSoup(
            '<img alt="Product photo" class="gallery-image" src="/img/product.jpg" />',
            "html.parser",
        )
        tag = soup.find("img")
        self.assertIsNotNone(tag)
        tag = cast(Tag, tag)
        _score, signal = self.service._score_by_keywords(tag, "https://x/product.jpg")

        self.assertEqual(signal, 0)

    def test_score_by_dimensions_penalizes_extreme_ratio(self):
        """Penalizes extremely wide or tall assets as likely non-label images."""
        score = self.service._score_by_dimensions(width=3000, height=300)
        self.assertLess(score, 0)

    def test_extract_html_nutrition_parses_table_text(self):
        """Extracts normalized text from known nutrition table selector."""
        html = """
            <table class="nutrition-info-table">
              <tr><th>Nutrient</th><th>Qty</th></tr>
              <tr><td>Protein</td><td>20g</td></tr>
            </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        text = self.service._extract_html_nutrition(soup)
        self.assertIn("Nutrient | Qty", text)
        self.assertIn("Protein | 20g", text)

    @patch("agents.tools.scraper.requests.get")
    def test_download_html_uses_requests_with_timeout(self, mock_get):
        """Downloads HTML text with expected HTTP options."""
        response = MagicMock()
        response.text = "<html></html>"
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        html = self.service._download_html("https://example.com")
        self.assertEqual(html, "<html></html>")
        kwargs = mock_get.call_args.kwargs
        self.assertEqual(kwargs["timeout"], 30)

    def test_check_hash_detects_duplicates(self):
        """Rejects repeated image hash in same candidate batch."""
        with patch.object(self.service, "_compute_phash", return_value="abc123"):
            seen: set[str] = set()
            first = self.service._check_hash(b"img", "u1", seen)
            second = self.service._check_hash(b"img", "u1", seen)

        self.assertTrue(first)
        self.assertFalse(second)

    def test_extract_image_sources_collects_img_and_jsonld(self):
        """Collects multiple image sources from HTML and JSON-LD."""
        html = """
            <img data-src="/a.jpg" />
            <meta property="og:image" content="/b.jpg" />
            <script type="application/ld+json">{"image": ["/c.jpg"]}</script>
        """
        soup = BeautifulSoup(html, "html.parser")
        sources = self.service._extract_image_sources(soup)
        srcs = [s[0] for s in sources]
        self.assertIn("/a.jpg", srcs)
        self.assertIn("/b.jpg", srcs)
        self.assertIn("/c.jpg", srcs)

    def test_extract_json_ld_images_ignores_invalid_payload(self):
        """Ignores invalid JSON-LD blocks without breaking extraction."""
        soup = BeautifulSoup(
            """
            <script type="application/ld+json">{invalid}</script>
            <script type="application/ld+json">{"image": "/ok.jpg"}</script>
            """,
            "html.parser",
        )
        sources: list[tuple[str, object]] = []
        self.service._extract_json_ld_images(soup, sources)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0][0], "/ok.jpg")

    def test_get_attr_joins_class_lists(self):
        """Normalizes list-valued HTML attributes to space-separated string."""
        soup = BeautifulSoup('<img class="a b c" />', "html.parser")
        tag = soup.find("img")
        self.assertIsNotNone(tag)
        tag = cast(Tag, tag)
        self.assertEqual(self.service._get_attr(tag, "class"), "a b c")

    def test_calculate_image_score_handles_invalid_image(self):
        """Falls back to keyword-only score when image bytes cannot be opened."""
        soup = BeautifulSoup('<img alt="nutrition" />', "html.parser")
        tag = soup.find("img")
        self.assertIsNotNone(tag)
        tag = cast(Tag, tag)

        with patch("agents.tools.scraper.Image.open", side_effect=OSError("bad")):
            score, width, height, signal, cv_score = (
                self.service._calculate_image_score(
                    tag, "https://x/nutrition.jpg", b"bad-bytes"
                )
            )

        self.assertEqual(width, 0)
        self.assertEqual(height, 0)
        self.assertGreater(score, 0)
        self.assertGreater(signal, 0)
        self.assertEqual(cv_score, 0.0)


class _MemoryStorage:
    """Simple in-memory storage double."""

    def __init__(self):
        self.uploads: dict[tuple[str, str], bytes] = {}
        self.content_types: dict[tuple[str, str], str] = {}

    def upload(self, bucket: str, key: str, content: bytes, content_type: str):
        """Store upload payload in memory."""
        self.uploads[(bucket, key)] = content
        self.content_types[(bucket, key)] = content_type

    def download(self, bucket: str, key: str) -> bytes:
        """Load payload from memory."""
        return self.uploads[(bucket, key)]


class TestScraperToolService(TestCase):
    """Tests for scraper service flow methods with DB interaction."""

    def setUp(self):
        """Create service with in-memory storage."""
        with patch("agents.tools.scraper.get_storage") as mock_storage:
            self.storage = _MemoryStorage()
            mock_storage.return_value = self.storage
            self.service = ScraperService()

    def test_download_assets_uploads_html_and_manifest(self):
        """Uploads source HTML and lightweight image manifest to storage."""
        with (
            patch.object(self.service, "_download_html", return_value="<html></html>"),
            patch.object(
                self.service,
                "_build_image_manifest",
                return_value={
                    "page_url": "https://example.com/p",
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "images": [{"url": "https://cdn/x.jpg", "position": 0}],
                },
            ),
            patch.object(self.service, "_extract_site_data", return_value={"x": 1}),
        ):
            base = self.service.download_assets(42, "https://example.com/p")

        self.assertEqual(base, "42/source.html")
        self.assertIn(("42", "source.html"), self.storage.uploads)
        self.assertIn(("42", "image_manifest.json"), self.storage.uploads)
        self.assertIn(("42", "site_data.json"), self.storage.uploads)
        manifest = json.loads(self.storage.uploads[("42", "image_manifest.json")])
        self.assertEqual(manifest["images"][0]["url"], "https://cdn/x.jpg")

    def test_download_assets_raises_on_processing_error(self):
        """Propagates failures from image processing step."""
        with (
            patch.object(self.service, "_download_html", return_value="<html></html>"),
            patch.object(
                self.service, "_build_image_manifest", side_effect=RuntimeError("x")
            ),
            self.assertRaises(RuntimeError),
        ):
            self.service.download_assets(8, "https://example.com/p")

    @patch("agents.tools.scraper.requests.get")
    def test_materialize_candidates_downloads_and_scores_manifest_images(
        self, mock_get
    ):
        """Builds candidates.json from manifest in heavy Dagster-side step."""
        self.storage.upload(
            "51",
            "image_manifest.json",
            json.dumps(
                {
                    "page_url": "https://example.com/p",
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "images": [
                        {
                            "position": 1,
                            "url": "https://example.com/p1.png",
                            "metadata": {"alt": "Nutrition facts"},
                        }
                    ],
                }
            ).encode("utf-8"),
            "application/json",
        )
        response = MagicMock()
        response.status_code = 200
        response.content = b"raw-image"
        mock_get.return_value = response

        with (
            patch.object(self.service, "_check_hash", return_value=True),
            patch.object(
                self.service,
                "_calculate_image_score",
                return_value=(20, 400, 400, 2, 0.8),
            ),
        ):
            candidates = self.service.materialize_candidates(
                "51", "https://example.com/p"
            )

        self.assertEqual(len(candidates), 1)
        self.assertIn(("51", "candidates.json"), self.storage.uploads)
        saved = json.loads(self.storage.uploads[("51", "candidates.json")])
        self.assertEqual(saved[0]["cv_table_score"], 0.8)

    def test_process_images_dedupes_and_sorts_candidates(self):
        """Dedupes repeated URLs and returns candidates sorted by score."""
        html = "<html><body></body></html>"
        soup = BeautifulSoup(
            '<img src="/one.jpg" /><img src="/two.jpg" />', "html.parser"
        )
        tag = soup.find("img")
        self.assertIsNotNone(tag)
        tag = cast(Tag, tag)
        second_tag = cast(Tag, soup.find_all("img")[1])

        with (
            patch.object(
                self.service,
                "_extract_image_sources",
                return_value=[
                    ("/one.jpg", tag),
                    ("/one.jpg", tag),
                    ("/two.jpg", second_tag),
                    ("", tag),
                ],
            ),
            patch.object(
                self.service,
                "_process_single_candidate",
                side_effect=[
                    {"file": "a", "score": 5},
                    {"file": "b", "score": 30},
                ],
            ) as mock_process,
        ):
            result = self.service._process_images(html, "https://example.com", "11")

        self.assertEqual([x["score"] for x in result], [30, 5])
        self.assertEqual(mock_process.call_count, 2)

    @patch("agents.tools.scraper.requests.get")
    def test_process_single_candidate_uses_mime_by_extension(self, mock_get):
        """Uploads image with MIME matching detected extension."""
        response = MagicMock()
        response.status_code = 200
        response.content = b"raw-image"
        mock_get.return_value = response

        soup = BeautifulSoup(
            '<img alt="Nutrition table" src="/x.png" />', "html.parser"
        )
        tag = soup.find("img")
        self.assertIsNotNone(tag)
        tag = cast(Tag, tag)

        with (
            patch.object(self.service, "_check_hash", return_value=True),
            patch.object(
                self.service,
                "_calculate_image_score",
                return_value=(20, 400, 400, 2, 0.7),
            ),
        ):
            candidate = self.service._process_single_candidate(
                1,
                "https://example.com/image.png",
                tag,
                "55",
                set(),
            )

        self.assertIsNotNone(candidate)
        candidate = cast(dict, candidate)
        self.assertEqual(
            self.storage.content_types[("55", "images/image_1.png")],
            "image/png",
        )
        self.assertEqual(candidate["cv_table_score"], 0.7)

    @patch("agents.tools.scraper.requests.get")
    def test_process_single_candidate_rejects_svg(self, mock_get):
        """Skips SVG images before upload."""
        response = MagicMock()
        response.status_code = 200
        response.content = b"svg-content"
        mock_get.return_value = response
        soup = BeautifulSoup(
            '<img alt="Nutrition table" src="/x.svg" />', "html.parser"
        )
        tag = soup.find("img")
        self.assertIsNotNone(tag)
        tag = cast(Tag, tag)

        with patch.object(self.service, "_check_hash", return_value=True):
            candidate = self.service._process_single_candidate(
                2, "https://example.com/image.svg", tag, "9", set()
            )

        self.assertIsNone(candidate)
        self.assertEqual(self.storage.uploads, {})

    @patch("agents.tools.scraper.requests.get")
    def test_process_single_candidate_fallbacks_unknown_extension(self, mock_get):
        """Uses jpg key/mime when extension is missing or invalid."""
        response = MagicMock()
        response.status_code = 200
        response.content = b"raw-image"
        mock_get.return_value = response
        soup = BeautifulSoup(
            '<img alt="Nutrition table" src="/x.abcdef" />', "html.parser"
        )
        tag = soup.find("img")
        self.assertIsNotNone(tag)
        tag = cast(Tag, tag)

        with (
            patch.object(self.service, "_check_hash", return_value=True),
            patch.object(
                self.service,
                "_calculate_image_score",
                return_value=(20, 400, 400, 2, 0.6),
            ),
        ):
            candidate = self.service._process_single_candidate(
                5, "https://example.com/image.abcdef?x=1", tag, "19", set()
            )

        self.assertIsNotNone(candidate)
        candidate = cast(dict, candidate)
        self.assertEqual(candidate["file"], "images/image_5.jpg")
        self.assertEqual(
            self.storage.content_types[("19", "images/image_5.jpg")],
            "image/jpeg",
        )

    def test_check_hash_returns_true_when_hash_fails(self):
        """Allows candidate when hash calculation fails."""
        with patch.object(self.service, "_compute_phash", side_effect=OSError("bad")):
            result = self.service._check_hash(
                b"img", "https://example.com/img.jpg", set()
            )
        self.assertTrue(result)

    def test_extract_metadata_downloads_html_and_uploads_data_json(self):
        """Extracts extruct metadata, appends custom nutrition text and persists JSON."""
        html = """
            <html>
              <body>
                <table class="nutrition-info-table">
                  <tr><th>Nutrient</th><th>Qty</th></tr>
                </table>
              </body>
            </html>
        """
        self.storage.upload("77", "source.html", html.encode("utf-8"), "text/html")

        with patch(
            "agents.tools.scraper.extruct.extract", return_value={"json-ld": []}
        ):
            data = self.service.extract_metadata(
                "77/source.html", "https://example.com/product"
            )

        self.assertIn("custom_nutrition_text", data)
        self.assertIn(("77", "data.json"), self.storage.uploads)
        saved = json.loads(self.storage.uploads[("77", "data.json")])
        self.assertIn("custom_nutrition_text", saved)

    def test_extract_metadata_raises_on_storage_failure(self):
        """Raises when source html cannot be loaded."""
        with self.assertRaises(KeyError):
            self.service.extract_metadata("1/missing.html", "https://example.com")

    def test_consolidate_uses_product_info_and_fallbacks(self):
        """Consolidates product metadata and keeps expected fallback behavior."""
        metadata = {
            "json-ld": [
                {"@type": "BreadcrumbList"},
                {
                    "@type": "Product",
                    "name": "Whey Pro",
                    "description": "Main product",
                    "brand": {"name": "Brand X"},
                    "image": ["https://cdn/x.jpg"],
                    "gtin13": "789123",
                    "category": "Supplements",
                },
            ],
            "opengraph": [{"og:title": "OG title", "og:description": "OG desc"}],
            "custom_nutrition_text": "Energia | 120",
        }
        result = self.service.consolidate(metadata, price=10.5, stock_status="A")

        self.assertEqual(result.name, "Whey Pro")
        self.assertEqual(result.brand_name, "Brand X")
        self.assertEqual(result.ean, "789123")
        self.assertEqual(result.image_url, "https://cdn/x.jpg")
        self.assertEqual(result.price, 10.5)
        self.assertIn("NUTRITION TABLE RAW TEXT", result.description or "")

    def test_consolidate_brand_override_and_unknown_defaults(self):
        """Uses override and defaults when Product JSON-LD is absent."""
        metadata = {"json-ld": [], "opengraph": [{"og:title": "OG Product"}]}
        result = self.service.consolidate(
            metadata, brand_name_override="Brand Override"
        )

        self.assertEqual(result.name, "OG Product")
        self.assertEqual(result.brand_name, "Brand Override")
        self.assertEqual(result.description, "")

    def test_extract_brand_and_image_url_variants(self):
        """Handles brand/image fields represented as strings, lists and missing values."""
        self.assertEqual(self.service._extract_brand({"brand": "ABC"}), "ABC")
        self.assertEqual(self.service._extract_brand({"brand": 10}), "Unknown Brand")
        self.assertEqual(
            self.service._extract_image_url({"image": []}, {"opengraph": [{}]}), None
        )
        self.assertEqual(
            self.service._extract_image_url({}, {"opengraph": [{"og:image": "x"}]}), "x"
        )
