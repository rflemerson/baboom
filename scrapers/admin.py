from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin

from .models import OpenFoodFactsData, ScrapedItem


@admin.action(description="Create/Merge Product from selected item")
def create_product_from_scraped_item(modeladmin, request, queryset):
    # Only allow one item at a time for this flow
    if queryset.count() > 1:
        modeladmin.message_user(
            request,
            _("Please select only one item to create a product from."),
            level=messages.WARNING,
        )
        return None

    item = queryset.first()

    # Initialize params with basic ScrapedItem data
    params = {
        "initial_name": item.name,
        "initial_ean": item.ean,
    }

    # Description
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


@admin.register(ScrapedItem)
class ScrapedItemAdmin(SimpleHistoryAdmin):
    list_display = [
        "external_id",
        "store_slug",
        "name",
        "price",
        "stock_status",
        "updated_at",
    ]
    list_filter = ["store_slug", "status", "stock_status"]
    search_fields = ["name", "external_id", "ean", "sku"]
    history_list_display = ["status"]
    actions = [create_product_from_scraped_item]


@admin.register(OpenFoodFactsData)
class OpenFoodFactsDataAdmin(admin.ModelAdmin):
    list_display = ["ean", "updated_at", "created_at"]
    search_fields = ["ean"]
    readonly_fields = ["created_at", "updated_at"]
