from unittest.mock import patch

from django.test import TestCase

# Import to force module load and coverage
from agents.flows.main_flow import (
    PipelineStep,
    analyze_task,
    download_task,
    product_ingestion_flow,
    upload_product_task,
)
from agents.schemas.analysis import ComboComponent, ProductAnalysisResult
from agents.schemas.product import RawScrapedData
from scrapers.models import ScrapedItem


class TestMainFlow(TestCase):
    """Test suite for the main ingestion flow."""

    def setUp(self):
        """Set up mock data."""
        # Create a mock ScrapedItem
        self.item = ScrapedItem.objects.create(
            store_slug="test-store",
            external_id="123",
            name="Test Product",
            product_link="http://example.com",
            price=10.0,
            status=ScrapedItem.Status.NEW,
        )

    @patch("agents.flows.main_flow.download_task")
    @patch("agents.flows.main_flow.analyze_task")
    @patch("agents.flows.main_flow.upload_product_task")
    def test_full_flow(self, mock_upload, mock_analyze, mock_download):
        """Test the full flow orchestrator."""
        # Setup mocks
        mock_download.return_value = "bucket/key"

        # analyze_task returns (RawScrapedData, ProductAnalysisResult, images)
        raw_data = RawScrapedData(
            name="Test Consolidated", brand_name="Brand", category="Test Category"
        )

        analysis = ProductAnalysisResult(name="Test Analyzed")

        imgs: list[str] = ["img1.jpg"]

        mock_analyze.return_value = (raw_data, analysis, imgs)

        # Run
        product_ingestion_flow(target_item_id=self.item.id, step=PipelineStep.FULL)

        # Verify
        mock_download.assert_called_once_with(self.item.id)
        mock_analyze.assert_called_once_with(self.item.id, "bucket/key")
        mock_upload.assert_called_once_with(self.item.id, raw_data, analysis, imgs)

    @patch("agents.flows.main_flow.ScraperService")
    def test_download_task(self, mock_service_cls):
        """Test download task."""
        mock_service = mock_service_cls.return_value
        mock_service.download_assets.return_value = "bucket/path"

        path = download_task(self.item.id)

        self.item.refresh_from_db()
        self.assertEqual(path, "bucket/path")
        self.assertEqual(self.item.status, ScrapedItem.Status.PROCESSING)

    @patch("agents.flows.main_flow.ScraperService")
    @patch("agents.flows.main_flow.get_storage")
    @patch("agents.flows.main_flow.run_raw_extraction")
    @patch("agents.flows.main_flow.run_groq_json_extraction")
    def test_analyze_task(self, mock_groq, mock_raw, mock_storage, mock_scraper_cls):
        """Test analyze task."""
        mock_storage_instance = mock_storage.return_value
        mock_storage_instance.download.return_value = (
            '[{"file": "img1.jpg", "score": 10}]'
        )

        mock_scraper = mock_scraper_cls.return_value
        mock_scraper.extract_metadata.return_value = {}
        # Emulate consolidate returning valid RawScrapedData
        mock_scraper.consolidate.return_value = RawScrapedData(
            name="Test Raw", brand_name="Brand", ean="1234567890123"
        )

        mock_groq.return_value = ProductAnalysisResult(name="Analyzed")

        analyze_task(self.item.id, "bucket/path")

        mock_raw.assert_called_once()
        mock_groq.assert_called_once()

    @patch("agents.flows.main_flow.product_create")
    def test_upload_task(self, mock_create):
        """Test upload task."""
        # Raw data here is what comes from consolidate -> RawScrapedData
        raw_data = RawScrapedData(
            name="Raw", brand_name="Brand", category="Test Category"
        )

        analysis = ProductAnalysisResult(
            name="Analyzed",
            packaging="CONTAINER",
            is_combo=True,
            components=[ComboComponent(name="Comp1", quantity=1)],
            nutrient_claims=["protein"],
        )
        imgs: list[str] = []

        upload_product_task(self.item.id, raw_data, analysis, imgs)

        mock_create.assert_called_once()
        _args, kwargs = mock_create.call_args
        data = kwargs["data"]
        self.assertEqual(data.name, "Analyzed")
        self.assertTrue(data.is_combo)
        self.assertEqual(len(data.components), 1)
        self.assertEqual(data.nutrient_claims, ["protein"])
