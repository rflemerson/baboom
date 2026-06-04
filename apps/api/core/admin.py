"""Django admin configuration for the core domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import nested_admin
from django.contrib import admin, messages
from django.db import transaction
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .admin_mappers import (
    build_product_create_input,
    build_product_metadata_update_input,
    build_store_listing_payloads,
    find_product_store_inline_formset,
)
from .forms import ProductAdminForm, ProductStoreInlineForm, ProductStoreInlineFormSet
from .models import (
    APIKey,
    Brand,
    Category,
    Flavor,
    Micronutrient,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductStore,
    Store,
    Tag,
)
from .services import (
    ProductCreateService,
    ProductMetadataUpdateService,
    ProductStoreService,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.forms import BaseInlineFormSet
    from django.http import HttpRequest, HttpResponse


class MicronutrientInline(nested_admin.NestedTabularInline):
    """Inline for micronutrients."""

    model = Micronutrient
    extra = 0
    min_num = 0
    classes: ClassVar[list[str]] = ["collapse"]


class ProductStoreInline(admin.TabularInline):
    """Official store listing workflow embedded in the product admin."""

    model = ProductStore
    form = ProductStoreInlineForm
    formset = ProductStoreInlineFormSet
    extra = 0
    autocomplete_fields: ClassVar[list[str]] = ["store"]
    fields = (
        "store",
        "external_id",
        "product_link",
        "affiliate_link",
        "price",
        "stock_status",
    )


class ProductNutritionInline(admin.TabularInline):
    """Inline for linking products to nutrition tables managed in the admin."""

    model = ProductNutrition
    extra = 0
    autocomplete_fields: ClassVar[list[str]] = ["nutrition_facts"]
    filter_horizontal: ClassVar[list[str]] = ["flavors"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for products."""

    INITIAL_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "ean",
        "description",
    )

    form = ProductAdminForm
    show_facets = admin.ShowFacets.ALWAYS
    list_display = (
        "name",
        "brand",
        "weight",
        "packaging",
        "get_category",
        "is_published",
        "created_at",
    )
    list_filter = ("brand", "packaging", "category", "tags", "is_published")
    search_fields = ("name", "brand__name")
    autocomplete_fields: ClassVar[list[str]] = ["brand", "tags", "category"]
    list_per_page = 20
    filter_horizontal: ClassVar[list[str]] = ["tags"]
    inlines: ClassVar[list[type[admin.TabularInline]]] = [
        ProductStoreInline,
        ProductNutritionInline,
    ]
    actions = ("delete_products_with_related_data",)
    save_on_top = True
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "brand",
                    "weight",
                    "ean",
                    "description",
                    "packaging",
                    "category",
                    "tags",
                    "is_published",
                ),
            },
        ),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset."""
        return (
            super()
            .get_queryset(request)
            .select_related("brand", "category")
            .prefetch_related("tags")
        )

    @admin.display(description="Categoria", ordering="category__name")
    def get_category(self, obj: Product) -> str:
        """Return category name."""
        return obj.category.name if obj.category else "-"

    def get_changeform_initial_data(self, request: HttpRequest) -> dict[str, str]:
        """Populate initial form data.

        Populate initial form data from GET parameters.
        Example: /admin/core/product/add/?initial_name=Whey&initial_ean=123
        """
        initial = super().get_changeform_initial_data(request)
        for key, value in request.GET.items():
            if key.startswith("initial_"):
                field_name = key.replace("initial_", "")
                if field_name in self.INITIAL_FIELDS:
                    initial[field_name] = value
        return initial

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        """Wrap the manager-facing product workflow in a single transaction."""
        with transaction.atomic():
            return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(
        self,
        _request: HttpRequest,
        obj: Product,
        form: ProductAdminForm,
        change: object,
    ) -> None:
        """Persist product changes through the official service layer."""
        if change:
            updated_product = ProductMetadataUpdateService().execute(
                product_id=obj.pk,
                data=build_product_metadata_update_input(form),
            )
            obj.pk = updated_product.pk
            obj.refresh_from_db()
            return

        created_product = ProductCreateService().execute(
            build_product_create_input(form),
        )
        obj.pk = created_product.pk
        obj.refresh_from_db()

    def save_related(
        self,
        request: HttpRequest,
        form: ProductAdminForm,
        formsets: list[BaseInlineFormSet],
        change: object,
    ) -> None:
        """Persist service-backed relations after the product itself is saved."""
        self._sync_product_store_listings(form.instance, formsets)
        for formset in formsets:
            if isinstance(formset, ProductStoreInlineFormSet):
                continue
            self.save_formset(request, form, formset, change)

    def _sync_product_store_listings(
        self,
        product: Product,
        formsets: list[BaseInlineFormSet],
    ) -> None:
        """Replace product store listings using the service-backed inline rows."""
        product_store_formset = find_product_store_inline_formset(formsets)
        if product_store_formset is None:
            return

        ProductStoreService().replace_listings(
            product,
            build_store_listing_payloads(product_store_formset),
        )

    @admin.action(
        description="Excluir products selecionados com links",
        permissions=["delete"],
    )
    def delete_products_with_related_data(
        self,
        request: HttpRequest,
        queryset: QuerySet[Product],
    ) -> None:
        """Delete selected products plus their store links.

        Merchant offers and their price observations are intentionally kept:
        they are raw observations that outlive any single catalog product.
        """
        products = list(queryset)
        if not products:
            return

        product_ids = [product.id for product in products]
        store_links = ProductStore.objects.filter(product_id__in=product_ids)

        with transaction.atomic():
            deleted_store_link_count, _ = store_links.delete()
            deleted_product_count, _ = Product.objects.filter(
                id__in=product_ids,
            ).delete()

        self.message_user(
            request,
            (
                "Excluded "
                f"{deleted_product_count} product(s) and "
                f"{deleted_store_link_count} store link(s)."
            ),
            level=messages.SUCCESS,
        )


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Admin for brands."""

    show_facets = admin.ShowFacets.ALWAYS
    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    list_per_page = 50


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    """Admin for stores."""

    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    list_per_page = 50


@admin.register(Flavor)
class FlavorAdmin(admin.ModelAdmin):
    """Admin for flavors."""

    list_display = ("name", "description")
    search_fields = ("name",)
    list_per_page = 50


@admin.register(Tag)
class TagAdmin(TreeAdmin):
    """Admin for tags."""

    form = movenodeform_factory(Tag)
    list_display = ("name", "description")
    search_fields = ("name",)
    list_per_page = 50


@admin.register(Category)
class CategoryAdmin(TreeAdmin):
    """Admin for categories."""

    form = movenodeform_factory(Category)
    list_display = ("name", "description")
    search_fields = ("name",)
    list_per_page = 50


@admin.register(ProductStore)
class ProductStoreAdmin(admin.ModelAdmin):
    """Technical support admin for product-store links."""

    show_facets = admin.ShowFacets.ALWAYS
    list_display = ("product", "store", "get_external_id", "get_last_price")
    list_filter = ("store",)
    search_fields = ("product__name", "store__name", "offer__external_id")
    autocomplete_fields: ClassVar[list[str]] = ["product", "store"]
    readonly_fields = (
        "product",
        "store",
        "offer",
        "affiliate_link",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset."""
        return (
            super()
            .get_queryset(request)
            .select_related("product", "store", "offer")
            .prefetch_related("offer__price_observations")
        )

    @admin.display(description="Store Product ID")
    def get_external_id(self, obj: ProductStore) -> str:
        """Return the merchant identifier from the linked offer."""
        return obj.external_id or "-"

    @admin.display(description="Last Price")
    def get_last_price(self, obj: ProductStore) -> str:
        """Return formatted last price from the linked offer."""
        if obj.offer is None:
            return "-"
        last = obj.offer.price_observations.first()
        return f"R$ {last.price}" if last else "-"

    def has_add_permission(self, _request: HttpRequest) -> bool:
        """Disallow direct creation; use ProductAdmin instead."""
        return False

    def has_delete_permission(
        self,
        _request: HttpRequest,
        _obj: ProductStore | None = None,
    ) -> bool:
        """Disallow direct deletion; use ProductAdmin instead."""
        return False


@admin.register(NutritionFacts)
class NutritionFactsAdmin(nested_admin.NestedModelAdmin):
    """Technical support admin for nutrition facts."""

    list_display = ("description", "serving_size_grams", "energy_kcal")
    search_fields = ("description",)
    inlines: ClassVar[list[type[nested_admin.NestedTabularInline]]] = [
        MicronutrientInline,
    ]
    list_per_page = 20

    def has_delete_permission(
        self,
        _request: HttpRequest,
        _obj: NutritionFacts | None = None,
    ) -> bool:
        """Disallow direct deletion from the technical support admin."""
        return False


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin for API keys."""

    list_display = ("name", "key", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("key", "created_at", "updated_at")
