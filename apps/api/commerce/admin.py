"""Admin for commercial identities.

Markets and the channel owner account are created by ingestion; a curator
reviews unresolved sellers, binds accounts to a merchant with evidence, and
registers payment methods and programmes.
"""

from __future__ import annotations

from django.contrib import admin

from .models import (
    Channel,
    Currency,
    FulfillmentProfile,
    Market,
    Merchant,
    MerchantBinding,
    PaymentMethod,
    PaymentProvider,
    Program,
    SellerAccount,
)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """ISO currencies and their precision."""

    list_display = ("code", "name", "minor_unit")
    search_fields = ("code", "name")


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    """Stores, marketplaces and apps."""

    list_display = ("name", "kind", "adapter")
    list_filter = ("kind",)
    search_fields = ("name",)


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    """A channel in one country and currency."""

    list_display = ("namespace", "channel", "country", "currency", "provenance")
    list_filter = ("country", "currency", "provenance")
    search_fields = ("namespace", "channel__name")


@admin.register(SellerAccount)
class SellerAccountAdmin(admin.ModelAdmin):
    """Sellers by market id; unresolved ones wait for review."""

    list_display = (
        "__str__",
        "market",
        "external_id",
        "is_channel_owner",
        "resolution",
    )
    list_filter = ("resolution", "is_channel_owner", "market")
    search_fields = ("name_raw", "external_id", "market__namespace")
    readonly_fields = ("market", "external_id", "is_channel_owner")


class MerchantBindingInline(admin.TabularInline):
    """Accounts a curator verified as the merchant's."""

    model = MerchantBinding
    extra = 0
    autocomplete_fields = ("seller_account",)


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    """A company grouping verified seller accounts."""

    list_display = ("name",)
    search_fields = ("name",)
    inlines = (MerchantBindingInline,)


@admin.register(FulfillmentProfile)
class FulfillmentProfileAdmin(admin.ModelAdmin):
    """Who ships, per market."""

    list_display = ("__str__", "market", "kind")
    list_filter = ("kind",)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """Payment methods by family and country."""

    list_display = ("code", "name", "family", "country")
    list_filter = ("family", "country")
    search_fields = ("code", "name")


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    """Acquirers, wallets, issuers and gateways."""

    list_display = ("name", "kind")
    search_fields = ("name",)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """Cashback, loyalty, membership, subscription and card programmes."""

    list_display = ("name", "kind", "issuer_channel", "issuer_seller", "issuer_name")
    list_filter = ("kind",)
    search_fields = ("name", "issuer_name")
