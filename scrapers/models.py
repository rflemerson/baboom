from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import ProductStore


class ScrapedItem(models.Model):
    class Status(models.TextChoices):
        NEW = "new", _("New")
        LINKED = "linked", _("Linked")
        IGNORED = "ignored", _("Ignored")

    url = models.URLField(unique=True, max_length=500)
    store = models.CharField(max_length=100, db_index=True)
    external_id = models.CharField(max_length=100, db_index=True)

    ean = models.CharField(
        max_length=14,
        blank=True,
        db_index=True,
        help_text=_("EAN/GTIN extracted from source"),
    )

    raw_data = models.JSONField(default=dict)

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

    def __str__(self):
        return f"[{self.store}] {self.external_id} - {self.status}"
