from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords


class ScrapedPage(models.Model):
    """Raw content of a scraped page."""

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
    raw_content = models.TextField(
        help_text=_("Raw HTML or JSON content"),
        blank=True,
        default="",
    )
    content_type = models.CharField(
        max_length=10,
        choices=[("HTML", "HTML"), ("JSON", "JSON")],
        default="HTML",
    )
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options."""

        ordering = ["-scraped_at"]
        indexes = [
            models.Index(fields=["url"]),
            models.Index(fields=["store_slug", "url"]),
        ]

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

    # product_link removed

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

    # Lazy reference to avoid circular imports
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

        constraints = [
            models.UniqueConstraint(
                fields=["store_slug", "external_id"],
                name="unique_scraped_item_identity",
            )
        ]
        indexes = [
            models.Index(fields=["store_slug", "external_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        """Return string representation."""
        return f"[{self.store_slug}] {self.external_id} - {self.get_stock_status_display()}"


class OpenFoodFactsData(models.Model):
    """Enriched data from Open Food Facts API."""

    ean = models.CharField(
        "EAN",
        max_length=14,
        unique=True,
        db_index=True,
        help_text="European Article Number / GTIN",
    )

    raw_data = models.JSONField(
        "Raw Open Food Facts Data",
        blank=True,
        null=True,
        help_text="Full JSON response from Open Food Facts API",
    )

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options."""

        verbose_name = "Open Food Facts Data"
        verbose_name_plural = "Open Food Facts Data"

    def __str__(self) -> str:
        """Return string representation."""
        return f"OFF Data for {self.ean}"
