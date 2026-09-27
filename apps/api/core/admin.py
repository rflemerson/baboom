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

from .dtos import ProductCreateInput, ProductMetadataUpdateInput
from .models import (
    Active,
    AlertSubscriber,
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
)
from .units import MASS_UNIT

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.forms import ModelForm
    from django.http import HttpRequest, HttpResponse


class NutritionActiveInline(nested_admin.NestedTabularInline):
    """Inline for the actives measured in a nutrition label."""

    model = NutritionActive
    extra = 0
    min_num = 0
    autocomplete_fields: ClassVar[list[str]] = ["active"]
    classes: ClassVar[list[str]] = ["collapse"]


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

    @admin.display(description=f"Net mass ({MASS_UNIT})", ordering="net_mass")
    def get_net_mass(self, obj: Product) -> str:
        """Return the mass as printed on the package."""
        if obj.net_mass is None:
            return "-"
        return f"{obj.net_mass:g}"

    @admin.display(description="Category", ordering="category__name")
    def get_category(self, obj: Product) -> str:
        """Return category name."""
        return obj.category.name if obj.category else "-"

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
        form: ModelForm,
        change: object,
    ) -> None:
        """Persist product changes through the official service layer."""
        if change:
            updated_product = ProductMetadataUpdateService().execute(
                product_id=obj.pk,
                data=ProductMetadataUpdateInput(
                    name=form.cleaned_data["name"],
                    net_mass=form.cleaned_data["net_mass"],
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

    list_display = ("name", "display_name", "scraper_slug", "products_count")
    search_fields = ("name", "display_name", "scraper_slug")
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

    list_display = ("nutrition_facts", "active", "amount", "declared_unit")
    list_filter = ("declared_unit", "active")
    search_fields = ("active__name", "nutrition_facts__description")
    autocomplete_fields: ClassVar[list[str]] = ["nutrition_facts", "active"]
    list_per_page = 50


@admin.register(ProductActive)
class ProductActiveAdmin(admin.ModelAdmin):
    """Read-only view of the concentrations derived from nutrition profiles."""

    list_display = ("nutrition_profile", "active", "fraction", "updated_at")
    list_filter = ("active",)
    search_fields = ("nutrition_profile__product__name", "active__name")
    readonly_fields = ("nutrition_profile", "active", "fraction")
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "nutrition_profile__product",
                "nutrition_profile__nutrition_facts",
                "active",
            )
        )

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
    """Link a captured offer to the catalog row it prices.

    This is the one place an offer becomes a price on the site. The curator
    picks the product, the label its flavor prints and the offer; the store,
    price, stock, URL and flavor all come from the offer itself.
    """

    show_facets = admin.ShowFacets.ALWAYS
    list_display = (
        "product",
        "nutrition_profile",
        "store",
        "get_flavors",
        "get_external_id",
        "get_current_price",
    )
    list_filter = ("store",)
    search_fields = ("product__name", "store__name", "offer__external_id")
    autocomplete_fields: ClassVar[list[str]] = [
        "product",
        "nutrition_profile",
        "offer",
    ]
    fields = ("product", "nutrition_profile", "offer", "affiliate_link", "store")
    readonly_fields = ("store",)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset."""
        return (
            super()
            .get_queryset(request)
            .select_related("product", "nutrition_profile", "store", "offer")
        )

    @admin.display(description="Flavors")
    def get_flavors(self, obj: ProductStore) -> str:
        """Return the flavors the linked offer states."""
        return ", ".join(obj.offer.flavors) if obj.offer else "-"

    @admin.display(description="Store Product ID")
    def get_external_id(self, obj: ProductStore) -> str:
        """Return the merchant identifier from the linked offer."""
        return obj.external_id or "-"

    @admin.display(description="Current Price")
    def get_current_price(self, obj: ProductStore) -> str:
        """Return the current price of the linked offer."""
        if obj.offer is None or obj.offer.current_price is None:
            return "-"
        return f"R$ {obj.offer.current_price}"


@admin.register(NutritionFacts)
class NutritionFactsAdmin(nested_admin.NestedModelAdmin):
    """Technical support admin for nutrition facts."""

    list_display = ("__str__", "serving_size", "energy", "used_by")
    search_fields = ("description", "content_hash")
    readonly_fields = ("used_by",)
    inlines: ClassVar[list[type[nested_admin.NestedTabularInline]]] = [
        NutritionActiveInline,
    ]
    list_per_page = 20

    @admin.display(description="Used by")
    def used_by(self, obj: NutritionFacts) -> str:
        """List every product label that prints this table.

        Editing the table rewrites all of them, so this is read before a write.
        """
        profiles = obj.product_profiles.select_related(
            "product",
            "nutrition_facts",
        ).prefetch_related("flavors")
        return "; ".join(str(profile) for profile in profiles) or "-"


@admin.register(AlertSubscriber)
class AlertSubscriberAdmin(admin.ModelAdmin):
    """Admin for price alert subscribers."""

    list_display = ("email", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("email",)
    list_per_page = 50
