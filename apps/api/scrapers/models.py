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
    html_structured_data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Structured metadata extracted from the product HTML"),
    )
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options."""

        ordering = ("-scraped_at",)
        indexes = (models.Index(fields=["store_slug", "url"]),)

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
    """Pipeline record tracking one merchant offer through the agent workflow.

    The offer identity, descriptive fields, price and stock now live on the
    linked :class:`offers.Offer`. This model holds only the cataloging pipeline
    state, so the daily scraper run no longer rewrites it (and its audit history
    only grows on genuine status transitions).
    """

    class Status(models.TextChoices):
        """Status of the scraped item in the pipeline."""

        NEW = "new", _("New")
        QUEUED = "queued", _("Queued for Agents")
        PROCESSING = "processing", _("Processing")
        LINKED = "linked", _("Linked")
        ERROR = "error", _("Error (Retry)")
        REVIEW = "review", _("Needs Review")
        IGNORED = "ignored", _("Ignored")

    offer = models.OneToOneField(
        "offers.Offer",
        on_delete=models.CASCADE,
        related_name="scraped_item",
        verbose_name=_("Merchant Offer"),
        help_text=_("Offer this pipeline record tracks"),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )

    error_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error_log = models.TextField(blank=True)

    source_page = models.ForeignKey(
        ScrapedPage,
        on_delete=models.CASCADE,
        related_name="items",
        null=True,
        blank=True,
        help_text=_("Source page where this item was found"),
    )

    class Meta:
        """Meta options."""

        indexes = (models.Index(fields=["status"]),)

    def __str__(self) -> str:
        """Return string representation."""
        return f"Pipeline[{self.get_status_display()}] for {self.offer}"


class ScrapedItemExtraction(BaseModel):
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

    class Meta:
        """Meta options."""

        ordering = ("-updated_at",)

    def __str__(self) -> str:
        """Return string representation."""
        return f"Extraction for scraped item {self.scraped_item_id}"
