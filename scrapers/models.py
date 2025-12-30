from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from core.models import ProductStore


class ScrapedItem(models.Model):
    class Status(models.TextChoices):
        NEW = "new", _("New")
        LINKED = "linked", _("Linked")
        IGNORED = "ignored", _("Ignored")

    class StockStatus(models.TextChoices):
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

    product_link = models.URLField(
        max_length=500,
        blank=True,
        help_text=_("URL to product page"),
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

    product_store = models.ForeignKey(
        ProductStore,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scraped_items",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
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
        return f"[{self.store_slug}] {self.external_id} - {self.get_stock_status_display()}"


class OpenFoodFactsData(models.Model):
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
        verbose_name = "Open Food Facts Data"
        verbose_name_plural = "Open Food Facts Data"

    def __str__(self) -> str:
        return f"OFF Data for {self.ean}"
