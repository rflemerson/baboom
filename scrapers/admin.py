from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin

from core.models import Product, ProductStore, Store

from .models import OpenFoodFactsData, ScrapedItem


class LinkProductForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        label=_("Target Product"),
        help_text=_("Select the product to link these items to."),
    )


@admin.action(description="🔍 Create/Merge Product from selected item")
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


@admin.action(description="🔗 Link to Product")
def link_to_product(modeladmin, request, queryset):
    # Step 2: Process the form
    if "apply" in request.POST:
        form = LinkProductForm(request.POST)
        if form.is_valid():
            target_product = form.cleaned_data["product"]
            linked_count = 0
            skipped_count = 0

            try:
                with transaction.atomic():
                    for item in queryset:
                        if not item.store_slug:
                            skipped_count += 1
                            continue

                        # Best effort Store find/create
                        store, _ = Store.objects.get_or_create(
                            name__iexact=item.store_slug,
                            defaults={
                                "name": item.store_slug,
                                "display_name": item.store_slug.title(),
                            },
                        )

                        # Update/Create ProductStore
                        p_store, _ = ProductStore.objects.update_or_create(
                            product=target_product,
                            store=store,
                            defaults={
                                "external_id": item.external_id,
                                "product_link": item.product_link,
                            },
                        )

                        # Update ScrapedItem
                        item.status = ScrapedItem.Status.LINKED
                        item.product_store = p_store
                        item.save()

                        linked_count += 1

                if linked_count > 0:
                    modeladmin.message_user(
                        request,
                        f"Successfully linked {linked_count} items to '{target_product}'.",
                        messages.SUCCESS,
                    )

                if skipped_count > 0:
                    modeladmin.message_user(
                        request,
                        f"Skipped {skipped_count} items (missing store slug).",
                        messages.WARNING,
                    )

                return redirect(request.get_full_path())

            except Exception as e:
                modeladmin.message_user(
                    request, f"Error linking products: {e}", messages.ERROR
                )
                # Fallthrough to re-render form on error if desired, or redirect.
                # Here we redirect to avoid partial state confusion, though transaction rollback helps.
                return redirect(request.get_full_path())

    # Step 1: Render form
    else:
        form = LinkProductForm()

    return render(
        request,
        "scrapers/link_product.html",
        {"items": queryset, "form": form, "title": "Link to Product"},
    )


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
    actions = [create_product_from_scraped_item, link_to_product]


@admin.register(OpenFoodFactsData)
class OpenFoodFactsDataAdmin(admin.ModelAdmin):
    list_display = ["ean", "updated_at", "created_at"]
    search_fields = ["ean"]
    readonly_fields = ["created_at", "updated_at"]
