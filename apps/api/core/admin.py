"""Django admin configuration for the core domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import nested_admin
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from offers.models import StockStatus

from .dtos import ProductCreateInput, ProductMetadataUpdateInput, StoreListingPayload
from .forms import ProductAdminForm, ProductStoreInlineForm, ProductStoreInlineFormSet
from .models import (
    Active,
    AlertSubscriber,
    APIKey,
    Brand,
    Category,
    Flavor,
    NutritionActive,
    NutritionFacts,
    Product,
    ProductActive,
    ProductComponent,
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
from .units import DISPLAY_MASS_UNIT, from_canonical

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.forms import BaseInlineFormSet
    from django.http import HttpRequest, HttpResponse


class NutritionActiveInline(nested_admin.NestedTabularInline):
    """Inline for the actives measured in a nutrition label."""

    model = NutritionActive
    extra = 0
    min_num = 0
    autocomplete_fields: ClassVar[list[str]] = ["active"]
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


class ProductComponentInline(admin.TabularInline):
    """Inline for building combo products from existing catalog items."""

    model = ProductComponent
    fk_name = "parent"
    extra = 0
    autocomplete_fields: ClassVar[list[str]] = ["component"]
    fields = ("component", "quantity")
    verbose_name = "Component"
    verbose_name_plural = "Components"


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
        "kind",
        "get_net_mass",
        "packaging",
        "get_category",
        "is_published",
        "created_at",
    )
    list_filter = ("kind", "brand", "packaging", "category", "tags", "is_published")
    search_fields = ("name", "brand__name")
    autocomplete_fields: ClassVar[list[str]] = ["brand", "tags", "category"]
    list_per_page = 20
    filter_horizontal: ClassVar[list[str]] = ["tags"]
    inlines: ClassVar[list[type[admin.TabularInline]]] = [
        ProductComponentInline,
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
                    "kind",
                    "brand",
                    "net_mass",
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

    @admin.display(description=f"Net mass ({DISPLAY_MASS_UNIT})", ordering="net_mass")
    def get_net_mass(self, obj: Product) -> str:
        """Return the stored canonical mass in the unit the catalog presents."""
        if obj.net_mass is None:
            return "-"
        return f"{from_canonical(obj.net_mass, DISPLAY_MASS_UNIT):g}"

    @admin.display(description="Category", ordering="category__name")
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
                data=ProductMetadataUpdateInput(
                    name=form.cleaned_data["name"],
                    net_mass=form.cleaned_data["net_mass"],
                    mass_unit=DISPLAY_MASS_UNIT,
                    brand_id=form.cleaned_data["brand"].id,
                    ean=form.cleaned_data["ean"],
                    description=form.cleaned_data["description"],
                    category_id=(
                        form.cleaned_data["category"].id
                        if form.cleaned_data["category"]
                        else None
                    ),
                    packaging=form.cleaned_data["packaging"],
                    is_published=form.cleaned_data["is_published"],
                    tag_ids=[tag.id for tag in form.cleaned_data["tags"]],
                ),
            )
            obj.pk = updated_product.pk
            obj.refresh_from_db()
            return

        created_product = ProductCreateService().execute(
            ProductCreateInput(
                name=form.cleaned_data["name"],
                net_mass=form.cleaned_data["net_mass"],
                mass_unit=DISPLAY_MASS_UNIT,
                brand_id=form.cleaned_data["brand"].id,
                category_id=(
                    form.cleaned_data["category"].id
                    if form.cleaned_data["category"]
                    else None
                ),
                ean=form.cleaned_data["ean"],
                description=form.cleaned_data["description"],
                packaging=form.cleaned_data["packaging"],
                is_published=form.cleaned_data["is_published"],
                tag_ids=[tag.id for tag in form.cleaned_data["tags"]],
            ),
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
        product_store_formset = next(
            (fs for fs in formsets if isinstance(fs, ProductStoreInlineFormSet)),
            None,
        )
        if product_store_formset is None:
            return

        store_listings_data: list[StoreListingPayload] = []
        for inline_form in product_store_formset.forms:
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
                    store_id=store.id,
                    external_id=cleaned_data.get("external_id") or "",
                    product_link=product_link,
                    affiliate_link=cleaned_data.get("affiliate_link") or "",
                    price=float(price),
                    stock_status=(
                        cleaned_data.get("stock_status") or StockStatus.AVAILABLE
                    ),
                ),
            )

        ProductStoreService().replace_listings(product, store_listings_data)

    @admin.action(
        description="Delete selected products with links",
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
    list_display = ("name", "display_name", "products_count")
    search_fields = ("name", "display_name")
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Annotate product count."""
        return super().get_queryset(request).annotate(product_count=Count("product"))

    @admin.display(description="Products", ordering="product_count")
    def products_count(self, obj: Brand) -> str:
        """Return the number of linked products with a link to the changelist."""
        url = reverse("admin:core_product_changelist") + f"?brand__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, obj.product_count)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    """Admin for stores."""

    list_display = ("name", "display_name", "products_count")
    search_fields = ("name", "display_name")
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Annotate product count."""
        return (
            super().get_queryset(request).annotate(product_count=Count("productstore"))
        )

    @admin.display(description="Products", ordering="product_count")
    def products_count(self, obj: Store) -> str:
        """Return the number of linked products with a link to the changelist."""
        url = reverse("admin:core_product_changelist") + f"?stores__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, obj.product_count)


@admin.register(Flavor)
class FlavorAdmin(admin.ModelAdmin):
    """Admin for flavors."""

    list_display = ("name", "description", "products_count")
    search_fields = ("name",)
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Annotate product count."""
        return (
            super()
            .get_queryset(request)
            .annotate(
                product_count=Count("productnutrition__product", distinct=True),
            )
        )

    @admin.display(description="Products", ordering="product_count")
    def products_count(self, obj: Flavor) -> str:
        """Return the number of linked products with a link to the changelist."""
        url = (
            reverse("admin:core_product_changelist")
            + f"?nutrition_profiles__flavors__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, obj.product_count)


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


@admin.register(ProductComponent)
class ProductComponentAdmin(admin.ModelAdmin):
    """Admin for product combo components."""

    list_display = ("parent", "component", "quantity")
    search_fields = ("parent__name", "component__name")
    autocomplete_fields: ClassVar[list[str]] = ["parent", "component"]
    list_per_page = 50


@admin.register(ProductNutrition)
class ProductNutritionAdmin(admin.ModelAdmin):
    """Admin for product nutrition links."""

    list_display = ("product", "nutrition_facts")
    search_fields = ("product__name", "nutrition_facts__description")
    autocomplete_fields: ClassVar[list[str]] = ["product", "nutrition_facts"]
    filter_horizontal: ClassVar[list[str]] = ["flavors"]
    list_per_page = 50


@admin.register(Active)
class ActiveAdmin(admin.ModelAdmin):
    """Admin for the substances the catalog ranks products by."""

    list_display = ("name", "slug", "display_unit", "nutrition_field")
    list_filter = ("display_unit",)
    search_fields = ("name", "slug")
    prepopulated_fields: ClassVar[dict[str, tuple[str, ...]]] = {"slug": ("name",)}
    list_per_page = 50


@admin.register(NutritionActive)
class NutritionActiveAdmin(admin.ModelAdmin):
    """Admin for the actives measured in a nutrition label."""

    list_display = ("nutrition_facts", "active", "declared_amount", "declared_unit")
    list_filter = ("declared_unit", "active")
    search_fields = ("active__name", "nutrition_facts__description")
    autocomplete_fields: ClassVar[list[str]] = ["nutrition_facts", "active"]
    list_per_page = 50


@admin.register(ProductActive)
class ProductActiveAdmin(admin.ModelAdmin):
    """Read-only view of the concentrations derived from nutrition profiles."""

    list_display = ("product", "active", "fraction", "updated_at")
    list_filter = ("active",)
    search_fields = ("product__name", "active__name")
    readonly_fields = ("product", "active", "fraction")
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset."""
        return super().get_queryset(request).select_related("product", "active")

    def has_add_permission(self, _request: HttpRequest) -> bool:
        """Disallow manual creation; rows are derived from nutrition data."""
        return False

    def has_change_permission(
        self,
        _request: HttpRequest,
        _obj: ProductActive | None = None,
    ) -> bool:
        """Disallow manual edits; rows are derived from nutrition data."""
        return False


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

    list_display = ("__str__", "serving_size", "energy")
    search_fields = ("description", "content_hash")
    inlines: ClassVar[list[type[nested_admin.NestedTabularInline]]] = [
        NutritionActiveInline,
    ]
    list_per_page = 20


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin for API keys."""

    list_display = ("name", "key", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("key", "created_at", "updated_at")


@admin.register(AlertSubscriber)
class AlertSubscriberAdmin(admin.ModelAdmin):
    """Admin for price alert subscribers."""

    list_display = ("email", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("email",)
    list_per_page = 50
