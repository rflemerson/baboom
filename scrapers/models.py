from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import ProductStore


class ScrapedItem(models.Model):
    class Status(models.TextChoices):
        NEW = "new", _("New (Pending)")
        LINKED = "linked", _("Linked (Active)")
        IGNORED = "ignored", _("Ignored")

    url = models.URLField(_("Product URL"), unique=True, max_length=500)
    store = models.CharField(_("Store Name"), max_length=100)
    external_id = models.CharField(_("External ID"), max_length=100)

    raw_data = models.JSONField(_("Raw Data"), default=dict)

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )

    product_store = models.ForeignKey(
        ProductStore,
        on_delete=models.SET_NULL,
        verbose_name=_("Linked Product"),
        null=True,
        blank=True,
        related_name="scraped_items",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Scraped Item")
        verbose_name_plural = _("Scraped Items")
        indexes = [
            models.Index(fields=["store", "external_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.store} - {self.external_id} [{self.status}]"
