"""Mapping helpers from Django admin forms to core service DTOs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from offers.models import StockStatus

from .dtos import (
    ProductCreateInput,
    ProductMetadataUpdateInput,
    StoreListingPayload,
)
from .forms import ProductStoreInlineFormSet

if TYPE_CHECKING:
    from django.forms import BaseInlineFormSet

    from .forms import ProductAdminForm


def build_product_create_input(form: ProductAdminForm) -> ProductCreateInput:
    """Build the creation DTO from the admin product form."""
    return ProductCreateInput(
        name=form.cleaned_data["name"],
        weight=form.cleaned_data["weight"],
        brand_name=form.cleaned_data["brand"].name,
        category_name=(
            form.cleaned_data["category"].name
            if form.cleaned_data["category"]
            else None
        ),
        ean=form.cleaned_data["ean"],
        description=form.cleaned_data["description"],
        packaging=form.cleaned_data["packaging"],
        is_published=form.cleaned_data["is_published"],
        tags=[tag.name for tag in form.cleaned_data["tags"]],
    )


def build_product_metadata_update_input(
    form: ProductAdminForm,
) -> ProductMetadataUpdateInput:
    """Build the metadata update DTO from the admin product form."""
    return ProductMetadataUpdateInput(
        name=form.cleaned_data["name"],
        description=form.cleaned_data["description"],
        category_name=(
            form.cleaned_data["category"].name if form.cleaned_data["category"] else ""
        ),
        packaging=form.cleaned_data["packaging"],
        is_published=form.cleaned_data["is_published"],
        tags=[tag.name for tag in form.cleaned_data["tags"]],
    )


def find_product_store_inline_formset(
    formsets: list[BaseInlineFormSet],
) -> ProductStoreInlineFormSet | None:
    """Return the product store inline formset when present."""
    return next(
        (
            formset
            for formset in formsets
            if isinstance(formset, ProductStoreInlineFormSet)
        ),
        None,
    )


def build_store_listing_payloads(
    formset: ProductStoreInlineFormSet,
) -> list[StoreListingPayload]:
    """Build store listing DTOs from the admin inline rows."""
    store_listings_data: list[StoreListingPayload] = []
    for inline_form in formset.forms:
        cleaned_data = getattr(inline_form, "cleaned_data", None)
        if not cleaned_data or cleaned_data.get("DELETE"):
            continue

        store = cleaned_data.get("store")
        product_link = cleaned_data.get("product_link")
        price = cleaned_data.get("price")
        if store is None or not product_link or price in (None, ""):
            continue

        store_listings_data.append(
            StoreListingPayload(
                store_name=store.display_name or store.name,
                external_id=cleaned_data.get("external_id") or "",
                product_link=product_link,
                affiliate_link=cleaned_data.get("affiliate_link") or "",
                price=float(price),
                stock_status=(
                    cleaned_data.get("stock_status") or StockStatus.AVAILABLE
                ),
            ),
        )

    return store_listings_data
