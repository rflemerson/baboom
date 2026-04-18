"""Admin registrations for scraper-related models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin

from .approval import ScrapedItemExtractionApproveService
from .models import ScrapedItem, ScrapedItemExtraction

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest, HttpResponseRedirect

NAME_SUMMARY_MAX_LENGTH = 40


def _format_validation_error(error: DjangoValidationError) -> str:
    """Return a compact validation message for Django admin feedback."""
    if hasattr(error, "message_dict"):
        return "; ".join(
            f"{field}: {', '.join(messages)}"
            for field, messages in error.message_dict.items()
        )
    return "; ".join(error.messages)


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

    params = {
        "initial_name": item.name,
        "initial_ean": item.ean,
    }

    desc_parts = []
    if item.store_slug:
        desc_parts.append(f"Imported from {item.store_slug}")
    if item.source_page:
        desc_parts.append(f"Link: {item.source_page.url}")

    if desc_parts:
        params["initial_description"] = "\n".join(desc_parts)

    query_string = urlencode(params)
    url = reverse("admin:core_product_add") + f"?{query_string}"
    return redirect(url)


@admin.action(description="Reset selected items to NEW")
def reset_to_new(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet[ScrapedItem],
) -> None:
    """Reset selected items to the NEW state."""
    updated = queryset.update(
        status=ScrapedItem.Status.NEW,
        error_count=0,
        last_attempt_at=None,
        last_error_log="",
    )
    modeladmin.message_user(
        request,
        _("%(count)s items reset to NEW for retrying.") % {"count": updated},
    )


@admin.action(description="Approve selected extractions into catalog")
def approve_extractions(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet[ScrapedItemExtraction],
) -> None:
    """Approve staged extractions by creating catalog products."""
    approved_count = 0
    service = ScrapedItemExtractionApproveService()

    for extraction in queryset.order_by("id"):
        try:
            service.execute(extraction_id=extraction.id)
        except DjangoValidationError as error:
            modeladmin.message_user(
                request,
                _("Extraction %(id)s was not approved: %(error)s")
                % {"id": extraction.id, "error": _format_validation_error(error)},
                level=messages.ERROR,
            )
            continue
        approved_count += 1

    if approved_count:
        modeladmin.message_user(
            request,
            _("%(count)s extraction(s) approved into the catalog.")
            % {"count": approved_count},
        )


@admin.register(ScrapedItem)
class ScrapedItemAdmin(SimpleHistoryAdmin):
    """Admin for scraped items."""

    list_display = (
        "id",
        "store_slug",
        "name_summary",
        "status",
        "error_count",
        "stock_status",
        "updated_at",
    )
    list_filter = ("status", "store_slug", "stock_status")
    search_fields = ("name", "external_id")

    readonly_fields = (
        "created_at",
        "updated_at",
        "last_attempt_at",
        "last_error_log",
        "product_store",
    )

    actions = (create_product_from_scraped_item, reset_to_new)

    @admin.display(description="Name")
    def name_summary(self, obj: ScrapedItem) -> str:
        """Truncate name for display."""
        return (
            obj.name[:NAME_SUMMARY_MAX_LENGTH] + "..."
            if obj.name and len(obj.name) > NAME_SUMMARY_MAX_LENGTH
            else obj.name
        )


@admin.register(ScrapedItemExtraction)
class ScrapedItemExtractionAdmin(admin.ModelAdmin):
    """Admin for staged agent extractions."""

    list_display = (
        "id",
        "scraped_item",
        "source_page",
        "root_product_name",
        "approved_product",
        "approved_at",
        "updated_at",
    )
    list_filter = ("approved_at", "scraped_item__store_slug")
    search_fields = (
        "scraped_item__name",
        "scraped_item__external_id",
        "source_page__url",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "approved_product",
        "approved_at",
    )
    actions = (approve_extractions,)

    @admin.display(description="Root product")
    def root_product_name(self, obj: ScrapedItemExtraction) -> str:
        """Return the extracted root product name for quick review."""
        name = obj.extracted_product.get("name", "")
        return str(name)
