"""Mapping helpers from Django admin forms to core service DTOs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dtos import (
    NutritionFactsPayload,
    ProductCreateInput,
    ProductMetadataUpdateInput,
    ProductNutritionPayload,
    StoreListingPayload,
)
from .forms import ProductStoreInlineFormSet
from .models import ProductPriceHistory

if TYPE_CHECKING:
    from django.forms import BaseInlineFormSet

    from .forms import ProductAdminForm
    from .models import NutritionFacts


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


def get_selected_existing_nutrition_facts(
    form: ProductAdminForm,
) -> NutritionFacts | None:
    """Return the explicitly selected nutrition table from the admin form."""
    return form.cleaned_data.get("existing_nutrition_facts")


def build_product_nutrition_payloads(
    form: ProductAdminForm,
) -> list[ProductNutritionPayload]:
    """Build nutrition payloads from the admin product form."""
    return [
        ProductNutritionPayload(
            nutrition_facts=NutritionFactsPayload(
                description=form.cleaned_data["nutrition_description"] or "",
                serving_size_grams=float(form.cleaned_data["serving_size_grams"]),
                energy_kcal=form.cleaned_data["energy_kcal"],
                proteins=float(form.cleaned_data["proteins"]),
                carbohydrates=float(form.cleaned_data["carbohydrates"]),
                total_fats=float(form.cleaned_data["total_fats"]),
                total_sugars=float(form.cleaned_data["total_sugars"] or 0),
                added_sugars=float(form.cleaned_data["added_sugars"] or 0),
                saturated_fats=float(form.cleaned_data["saturated_fats"] or 0),
                trans_fats=float(form.cleaned_data["trans_fats"] or 0),
                dietary_fiber=float(form.cleaned_data["dietary_fiber"] or 0),
                sodium=float(form.cleaned_data["sodium"] or 0),
            ),
        ),
    ]


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
                    cleaned_data.get("stock_status")
                    or ProductPriceHistory.StockStatus.AVAILABLE
                ),
            ),
        )

    return store_listings_data
