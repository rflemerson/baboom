"""Admin for policies, quotes and the observed costs pricing reads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from .models import (
    CurrencyConversionQuote,
    OfferScenarioProjection,
    PricingPolicyRevision,
    PricingQuote,
    QuoteLine,
    ShippingQuote,
    TaxFeeQuote,
)

if TYPE_CHECKING:
    from django.http import HttpRequest


class ReadOnlyAdmin(admin.ModelAdmin):
    """Computed or observed rows: inspected, never edited."""

    def has_add_permission(self, _request: HttpRequest) -> bool:
        """Rows come from services and adapters."""
        return False

    def has_change_permission(
        self,
        _request: HttpRequest,
        _obj: object = None,
    ) -> bool:
        """Rows are never edited."""
        return False


@admin.register(PricingPolicyRevision)
class PricingPolicyRevisionAdmin(admin.ModelAdmin):
    """What each public scenario counts; published versions are frozen."""

    list_display = ("__str__", "scenario", "market", "is_default", "published_at")
    list_filter = ("scenario", "is_default")


class QuoteLineInline(admin.TabularInline):
    """The offers of a quote."""

    model = QuoteLine
    extra = 0
    can_delete = False
    readonly_fields = ("offer", "quantity", "base_amount", "allocated_discount")


@admin.register(PricingQuote)
class PricingQuoteAdmin(ReadOnlyAdmin):
    """Kept quotes and the snapshot that reproduces each."""

    list_display = ("__str__", "merchandise_total", "total_payable", "engine_version")
    list_filter = ("policy", "engine_version")
    inlines = (QuoteLineInline,)


@admin.register(OfferScenarioProjection)
class OfferScenarioProjectionAdmin(ReadOnlyAdmin):
    """What the ranking reads, per offer and policy."""

    list_display = ("offer", "policy", "status", "amount", "computed_at", "expires_at")
    list_filter = ("policy", "status")
    search_fields = ("offer__name", "offer__external_id")


@admin.register(ShippingQuote)
class ShippingQuoteAdmin(ReadOnlyAdmin):
    """Quoted shipping, per group and destination."""

    list_display = ("__str__", "seller_account", "country", "observed_at", "expires_at")


@admin.register(TaxFeeQuote)
class TaxFeeQuoteAdmin(ReadOnlyAdmin):
    """Quoted taxes and fees."""

    list_display = ("__str__", "inclusion", "observed_at")


@admin.register(CurrencyConversionQuote)
class CurrencyConversionQuoteAdmin(admin.ModelAdmin):
    """Display rates; a curator may record one with its source."""

    list_display = ("__str__", "source", "observed_at", "valid_until")
