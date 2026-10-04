"""Admin for policies, quotes and the observed costs pricing reads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .invalidation import Repricing
from .models import (
    OfferScenarioProjection,
    PricingPolicyRevision,
    PricingQuote,
    QuoteLine,
    ShippingQuote,
    TaxFeeQuote,
)
from .replay import QuoteReplay

if TYPE_CHECKING:
    from django.db.models import QuerySet
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

    def save_model(
        self,
        request: HttpRequest,
        obj: PricingPolicyRevision,
        form: object,
        change: object,
    ) -> None:
        """Project a published policy for every linked offer."""
        super().save_model(request, obj, form, change)
        if obj.published_at is not None:
            Repricing().offers(None)


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
    actions = ("replay",)

    @admin.action(description=_("Replay from the snapshot"))
    def replay(self, request: HttpRequest, queryset: QuerySet[PricingQuote]) -> None:
        """Evaluate each quote again from its snapshot and report what differs."""
        replay = QuoteReplay()
        reproduced, differ, unsupported = 0, [], 0
        for quote in queryset:
            try:
                if replay.reproduces(quote):
                    reproduced += 1
                else:
                    differ.append(str(quote.pk))
            except ValueError:
                unsupported += 1
        self.message_user(
            request,
            f"{reproduced} reproduced; differ: {', '.join(differ) or 'none'}; "
            f"other engine version: {unsupported}",
            messages.SUCCESS if not differ else messages.WARNING,
        )


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
