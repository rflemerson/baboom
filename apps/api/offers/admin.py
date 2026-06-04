"""Admin registrations for the offers (pricing) domain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from .models import Offer, PriceObservation

if TYPE_CHECKING:
    from .models import Offer as OfferType

NAME_SUMMARY_MAX_LENGTH = 40


class PriceObservationInline(admin.TabularInline):
    """Read-only inline of the price series for an offer."""

    model = PriceObservation
    extra = 0
    can_delete = False
    readonly_fields = ("price", "stock_status", "observed_at")
    ordering = ("-observed_at",)

    def has_add_permission(self, _request: object, _obj: object = None) -> bool:
        """Price observations are appended by the scraper, never by hand."""
        return False


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    """Admin for merchant offers."""

    list_display = (
        "id",
        "store_slug",
        "name_summary",
        "external_id",
        "current_price",
        "current_stock_status",
        "updated_at",
    )
    list_filter = ("store_slug", "current_stock_status")
    search_fields = ("name", "external_id", "ean", "sku")
    readonly_fields = ("created_at", "updated_at")
    inlines = (PriceObservationInline,)

    @admin.display(description="Name")
    def name_summary(self, obj: OfferType) -> str:
        """Truncate name for display."""
        return (
            obj.name[:NAME_SUMMARY_MAX_LENGTH] + "..."
            if obj.name and len(obj.name) > NAME_SUMMARY_MAX_LENGTH
            else obj.name
        )


@admin.register(PriceObservation)
class PriceObservationAdmin(admin.ModelAdmin):
    """Admin for the raw price series."""

    list_display = ("id", "offer", "price", "stock_status", "observed_at")
    list_filter = ("stock_status", "observed_at")
    search_fields = ("offer__name", "offer__external_id")
    readonly_fields = ("offer", "price", "stock_status", "observed_at")
    ordering = ("-observed_at",)
