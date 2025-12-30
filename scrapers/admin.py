from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import OpenFoodFactsData, ScrapedItem


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


@admin.register(OpenFoodFactsData)
class OpenFoodFactsDataAdmin(admin.ModelAdmin):
    list_display = ["ean", "updated_at", "created_at"]
    search_fields = ["ean"]
    readonly_fields = ["created_at", "updated_at"]
