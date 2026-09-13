"""Database models for scraper state and imported payloads."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel


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
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options."""

        ordering = ("-scraped_at",)

    def __str__(self) -> str:
        """Return string representation."""
        return f"[{self.store_slug}] {self.url}"


class ScraperRun(models.Model):
    """Auditable execution record for scheduled scraper monitor tasks."""

    class Status(models.TextChoices):
        """Lifecycle status for a scraper run."""

        RUNNING = "running", _("Running")
        SUCCESS = "success", _("Success")
        ERROR = "error", _("Error")

    label = models.CharField(max_length=100, db_index=True)
    task_name = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    items_count = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        """Meta options."""

        ordering = ("-started_at",)
        indexes = (
            models.Index(fields=["label", "-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        )

    def __str__(self) -> str:
        """Return string representation."""
        started_at = self.started_at.strftime("%Y-%m-%d %H:%M:%S")
        return f"{self.label} - {self.get_status_display()} at {started_at}"


class ScrapedItem(BaseModel):
    """A merchant offer and the source page captured by the scraper."""

    offer = models.OneToOneField(
        "offers.Offer",
        on_delete=models.CASCADE,
        related_name="scraped_item",
        verbose_name=_("Merchant Offer"),
        help_text=_("Offer observed by the scraper"),
    )

    variant_context = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Which unit of the source page this offer is, in the store's words",
        ),
    )
    source_page = models.ForeignKey(
        ScrapedPage,
        on_delete=models.CASCADE,
        related_name="items",
        null=True,
        blank=True,
        help_text=_("Source page where this item was found"),
    )

    def __str__(self) -> str:
        """Return string representation."""
        return f"Scraped item for {self.offer}"
