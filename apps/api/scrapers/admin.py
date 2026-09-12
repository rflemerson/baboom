"""Admin registrations for scraper-related models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _

from .models import ScrapedItem, ScrapedPage, ScraperRun

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest, HttpResponseRedirect

NAME_SUMMARY_MAX_LENGTH = 40
ERROR_SUMMARY_MAX_LENGTH = 80


@admin.action(description="Open product creation from selected item")
def create_product_from_scraped_item(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet[ScrapedItem],
) -> HttpResponseRedirect | None:
    """Open the product admin add form prefilled from a scraped item."""
    item = queryset.first()
    if item is None:
        modeladmin.message_user(
            request,
            _("Please select one item first."),
            level=messages.WARNING,
        )
        return None

    if queryset.count() > 1:
        modeladmin.message_user(
            request,
            _("Please select only one item to create a product from."),
            level=messages.WARNING,
        )
        return None

    offer = item.offer
    linked_product = getattr(offer, "product_store", None)
    if linked_product is not None:
        return redirect(
            reverse("admin:core_product_change", args=[linked_product.product_id]),
        )

    query_string = urlencode({"source_offer": offer.pk})
    url = reverse("admin:core_product_add") + f"?{query_string}"
    return redirect(url)


@admin.register(ScrapedItem)
class ScrapedItemAdmin(admin.ModelAdmin):
    """Admin for scraped items."""

    list_display = (
        "id",
        "get_store_slug",
        "name_summary",
        "get_stock_status",
        "updated_at",
    )
    list_filter = ("offer__store_slug", "offer__current_stock_status")
    search_fields = ("offer__name", "offer__external_id")

    readonly_fields = (
        "created_at",
        "updated_at",
        "offer",
    )

    actions = (create_product_from_scraped_item,)

    def get_queryset(self, request: HttpRequest) -> QuerySet[ScrapedItem]:
        """Load the linked offer used across list columns."""
        return super().get_queryset(request).select_related("offer")

    @admin.display(description="Store", ordering="offer__store_slug")
    def get_store_slug(self, obj: ScrapedItem) -> str:
        """Return the store slug from the linked offer."""
        return obj.offer.store_slug

    @admin.display(description="Stock", ordering="offer__current_stock_status")
    def get_stock_status(self, obj: ScrapedItem) -> str:
        """Return the stock status from the linked offer."""
        return obj.offer.get_current_stock_status_display()

    @admin.display(description="Name")
    def name_summary(self, obj: ScrapedItem) -> str:
        """Truncate the offer name for display."""
        name = obj.offer.name
        return (
            name[:NAME_SUMMARY_MAX_LENGTH] + "..."
            if name and len(name) > NAME_SUMMARY_MAX_LENGTH
            else name
        )


@admin.register(ScrapedPage)
class ScrapedPageAdmin(admin.ModelAdmin):
    """Allow human inspection of captured metadata and rendered HTML."""

    list_display = ("url", "store_slug", "scraped_at", "updated_at")
    list_filter = ("store_slug",)
    search_fields = ("url",)
    readonly_fields = (
        "store_slug",
        "url",
        "api_context",
        "html_structured_data",
        "raw_html",
        "response_meta",
        "scraped_at",
        "updated_at",
    )

    def has_add_permission(self, _request: HttpRequest) -> bool:
        """Disallow manual creation of scraper-captured pages."""
        return False


@admin.register(ScraperRun)
class ScraperRunAdmin(admin.ModelAdmin):
    """Admin for scraper execution history."""

    list_display = (
        "id",
        "label",
        "status",
        "items_count",
        "started_at",
        "finished_at",
        "duration_ms",
        "error_summary",
    )
    list_filter = ("status", "label", "started_at")
    search_fields = ("label", "task_name", "message", "error_message")
    readonly_fields = (
        "label",
        "task_name",
        "status",
        "started_at",
        "finished_at",
        "duration_ms",
        "items_count",
        "message",
        "error_message",
    )
    ordering = ("-started_at",)

    @admin.display(description="Error")
    def error_summary(self, obj: ScraperRun) -> str:
        """Return a compact error preview for list display."""
        if not obj.error_message:
            return ""
        return (
            obj.error_message[:ERROR_SUMMARY_MAX_LENGTH] + "..."
            if len(obj.error_message) > ERROR_SUMMARY_MAX_LENGTH
            else obj.error_message
        )
