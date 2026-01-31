from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin

from .models import OpenFoodFactsData, ScrapedItem


@admin.action(description="Create/Merge Product from selected item")
def create_product_from_scraped_item(modeladmin, request, queryset):
    """Admin action to create products from scraped items."""
    if queryset.count() > 1:
        modeladmin.message_user(
            request,
            _("Please select only one item to create a product from."),
            level=messages.WARNING,
        )
        return None

    item = queryset.first()

    params = {
        "initial_name": item.name,
        "initial_ean": item.ean,
    }

    desc_parts = []
    if item.store_slug:
        desc_parts.append(f"Imported from {item.store_slug}")
    if item.product_link:
        desc_parts.append(f"Link: {item.product_link}")

    if desc_parts:
        params["initial_description"] = "\n".join(desc_parts)

    query_string = urlencode(params)
    url = reverse("admin:core_product_add") + f"?{query_string}"
    return redirect(url)


@admin.action(description="Reset selected items to NEW")
def reset_to_new(modeladmin, request, queryset):
    """Action to manually retry failed items."""
    updated = queryset.update(
        status=ScrapedItem.Status.NEW, error_count=0, last_error_log=""
    )
    modeladmin.message_user(request, f"{updated} items reset to NEW for retrying.")


@admin.register(ScrapedItem)
class ScrapedItemAdmin(SimpleHistoryAdmin):
    """Admin for scraped items."""

    list_display = [
        "id",
        "store_slug",
        "name_summary",
        "status",
        "error_count",
        "stock_status",
        "updated_at",
    ]
    list_filter = ["status", "store_slug", "stock_status"]
    search_fields = ["name", "external_id", "product_link"]

    readonly_fields = [
        "created_at",
        "updated_at",
        "last_attempt_at",
        "last_error_log",
        "product_store",
    ]

    actions = [create_product_from_scraped_item, reset_to_new]

    @admin.display(description="Name")
    def name_summary(self, obj):
        """Truncate name for display."""
        return (obj.name[:40] + "...") if obj.name and len(obj.name) > 40 else obj.name


@admin.register(OpenFoodFactsData)
class OpenFoodFactsDataAdmin(admin.ModelAdmin):
    """Admin for Open Food Facts Data."""

    list_display = ["ean", "updated_at", "created_at"]
    search_fields = ["ean"]
    readonly_fields = ["created_at", "updated_at"]
