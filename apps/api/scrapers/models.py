"""Database models for scraper state and imported payloads."""

from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords


class ScrapedPage(models.Model):
    """Structured context collected for a scraped page."""

    store_slug = models.CharField(
        max_length=100,
        db_index=True,
        help_text=_("Store identifier"),
    )
    url = models.URLField(
        max_length=500,
        unique=True,
        help_text=_("Page URL"),
    )
    api_context = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Normalized product context collected from store APIs"),
    )
    html_structured_data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Structured metadata extracted from the product HTML"),
    )
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options."""

        ordering = ("-scraped_at",)
        indexes = (
            models.Index(fields=["url"]),
            models.Index(fields=["store_slug", "url"]),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return f"[{self.store_slug}] {self.url}"


class ScrapedItem(models.Model):
    """Product data scraped from external sources."""

    class Status(models.TextChoices):
        """Status of the scraped item in the pipeline."""

        NEW = "new", _("New")
        PROCESSING = "processing", _("Processing")
        LINKED = "linked", _("Linked")
        ERROR = "error", _("Error (Retry)")
        DISCARDED = "discarded", _("Discarded (Junk)")
        REVIEW = "review", _("Needs Review")
        IGNORED = "ignored", _("Ignored")

    class StockStatus(models.TextChoices):
        """Stock availability status."""

        AVAILABLE = "A", _("Available")
        LAST_UNITS = "L", _("Last Units")
        OUT_OF_STOCK = "O", _("Out of Stock")

    store_slug = models.CharField(
        max_length=100,
        db_index=True,
        help_text=_("Store identifier"),
    )

    external_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text=_("Unique ID from Store"),
    )

    name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Name extracted from source"),
    )

    category = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Category/Department extracted from source"),
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    stock_quantity = models.IntegerField(
        blank=True,
        null=True,
        help_text=_("Available quantity in stock"),
    )

    stock_status = models.CharField(
        max_length=1,
        blank=True,
        choices=StockStatus.choices,
        default=StockStatus.AVAILABLE,
    )

    pid = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Product ID extracted from source"),
    )

    ean = models.CharField(
        max_length=14,
        blank=True,
        db_index=True,
        help_text=_("EAN/GTIN extracted from source"),
    )

    sku = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text=_("SKU extracted from source"),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )

    error_count = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error_log = models.TextField(blank=True)

    product_store = models.ForeignKey(
        "core.ProductStore",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scraped_items",
    )

    source_page = models.ForeignKey(
        ScrapedPage,
        on_delete=models.CASCADE,
        related_name="items",
        null=True,
        blank=True,
        help_text=_("Source page where this item was found"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        """Meta options."""

        constraints = (
            models.UniqueConstraint(
                fields=["store_slug", "external_id"],
                name="unique_scraped_item_identity",
            ),
        )
        indexes = (
            models.Index(fields=["store_slug", "external_id"]),
            models.Index(fields=["status"]),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"[{self.store_slug}] {self.external_id} - "
            f"{self.get_stock_status_display()}"
        )


class ScrapedItemExtraction(models.Model):
    """Agent extraction staged for human/backend catalog review."""

    scraped_item = models.OneToOneField(
        ScrapedItem,
        on_delete=models.CASCADE,
        related_name="agent_extraction",
        help_text=_("Scraped item that produced this extraction"),
    )
    source_page = models.ForeignKey(
        ScrapedPage,
        on_delete=models.CASCADE,
        related_name="agent_extractions",
        help_text=_("Source page used by the agent pipeline"),
    )
    image_report = models.TextField(
        blank=True,
        help_text=_("Ordered text report extracted from product images"),
    )
    extracted_product = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Recursive product tree returned by the agent"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options."""

        ordering = ("-updated_at",)

    def __str__(self) -> str:
        """Return string representation."""
        return f"Extraction for scraped item {self.scraped_item_id}"
