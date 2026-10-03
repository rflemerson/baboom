"""Admin registrations for the offers (pricing) domain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from .models import (
    AvailabilityObservation,
    CollectionCoverage,
    Evidence,
    FeaturedOfferObservation,
    Listing,
    ListingVariant,
    ObservationBatch,
    Offer,
    OfferPriceObservation,
    OfferSourceIdentity,
    PriceObservation,
)

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


class OfferPriceObservationInline(admin.TabularInline):
    """Typed prices of the offer, newest first."""

    model = OfferPriceObservation
    fk_name = "offer"
    extra = 0
    can_delete = False
    ordering = ("-observed_at",)
    fields = (
        "role",
        "amount",
        "currency",
        "payment_scope",
        "payment_method",
        "payment_label_raw",
        "installment_count",
        "source_field",
        "observed_at",
    )
    readonly_fields = fields

    def has_add_permission(self, _request: object, _obj: object = None) -> bool:
        """Observations are appended by ingestion."""
        return False


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    """Admin for merchant offers."""

    list_display = (
        "id",
        "store_slug",
        "name_summary",
        "get_flavors",
        "external_id",
        "current_price",
        "current_stock_status",
        "delisted_at",
        "updated_at",
    )
    list_filter = ("store_slug", "current_stock_status", "item_condition")
    # The admin API exposes no filter for a free-text column, so the store is
    # searched: "growth whey" narrows to Growth offers that mention whey.
    search_fields = ("store_slug", "name", "external_id", "ean", "sku")
    readonly_fields = (
        "listing_variant",
        "seller_account",
        "fulfillment_profile",
        "created_at",
        "updated_at",
    )
    inlines = (OfferPriceObservationInline, PriceObservationInline)

    @admin.display(description="Flavors")
    def get_flavors(self, obj: OfferType) -> str:
        """Return the flavors the store published for the unit."""
        return ", ".join(obj.flavors) or "-"

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


class ListingVariantInline(admin.TabularInline):
    """The selectable units of a listing, as the source published them."""

    model = ListingVariant
    extra = 0
    can_delete = False
    readonly_fields = ("external_id", "options", "selection", "gtin")

    def has_add_permission(self, _request: object, _obj: object = None) -> bool:
        """Variants come from ingestion."""
        return False


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    """Pages and advertisements markets publish."""

    list_display = ("__str__", "market", "external_id", "catalog_product_id")
    list_filter = ("market",)
    search_fields = ("title", "external_id", "catalog_product_id", "url")
    readonly_fields = ("market", "external_id", "url", "title", "catalog_product_id")
    inlines = (ListingVariantInline,)


@admin.register(ListingVariant)
class ListingVariantAdmin(admin.ModelAdmin):
    """Selectable units, searched by listing or GTIN."""

    list_display = ("__str__", "external_id", "gtin")
    search_fields = ("listing__title", "external_id", "gtin")
    readonly_fields = ("listing", "external_id", "options", "selection", "gtin")


@admin.register(OfferSourceIdentity)
class OfferSourceIdentityAdmin(admin.ModelAdmin):
    """Every name a source gives an offer."""

    list_display = ("__str__", "offer")
    list_filter = ("scheme", "namespace")
    search_fields = ("key",)
    readonly_fields = ("offer", "namespace", "scheme", "scheme_version", "key")


@admin.register(FeaturedOfferObservation)
class FeaturedOfferObservationAdmin(admin.ModelAdmin):
    """Which offer a listing variant featured, when."""

    list_display = ("listing_variant", "offer", "observed_at")
    readonly_fields = ("listing_variant", "offer", "observed_at")


class ReadOnlyAdmin(admin.ModelAdmin):
    """An append-only fact: inspected, never edited."""

    def has_add_permission(self, _request: object) -> bool:
        """Facts come from ingestion."""
        return False

    def has_change_permission(self, _request: object, _obj: object = None) -> bool:
        """Facts are never edited."""
        return False


@admin.register(OfferPriceObservation)
class OfferPriceObservationAdmin(ReadOnlyAdmin):
    """Every typed price, filterable by meaning."""

    list_display = (
        "offer",
        "role",
        "amount",
        "currency",
        "payment_scope",
        "payment_method",
        "installment_count",
        "semantics",
        "observed_at",
    )
    list_filter = ("role", "payment_scope", "semantics", "capture_stage")
    search_fields = ("offer__name", "offer__external_id", "source_field")


@admin.register(AvailabilityObservation)
class AvailabilityObservationAdmin(ReadOnlyAdmin):
    """Stock readings."""

    list_display = ("offer", "status", "quantity", "observed_at")
    list_filter = ("status",)


class CollectionCoverageInline(admin.TabularInline):
    """How completely each dimension was read."""

    model = CollectionCoverage
    extra = 0
    can_delete = False
    readonly_fields = ("dimension", "partition", "status", "reason", "cursor")


@admin.register(ObservationBatch)
class ObservationBatchAdmin(ReadOnlyAdmin):
    """Values read together, and their coverage."""

    list_display = ("__str__", "adapter", "status", "started_at", "finished_at")
    list_filter = ("adapter", "status")
    inlines = (CollectionCoverageInline,)


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    """What facts rest on; a curator may record a manual reading."""

    list_display = ("__str__", "kind", "observed_at", "captured_by")
    list_filter = ("kind",)
    search_fields = ("source_url", "excerpt")
