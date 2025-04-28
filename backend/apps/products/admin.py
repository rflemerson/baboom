from unfold.admin import ModelAdmin, TabularInline
from django.contrib import admin
from django.utils.html import format_html

from simple_history.admin import SimpleHistoryAdmin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import (
    Brand,
    Store,
    Flavor,
    Tag,
    Category,
    Product,
    ProductStore,
    ProductPriceHistory,
    NutritionalInfo,
    AdditionalNutrient,
    ProductFlavorNutritionalInfo,
)


class ProductStoreInline(TabularInline):
    model = ProductStore
    tab = True
    extra = 0


class ProductFlavorNutritionalInfoInline(TabularInline):
    model = ProductFlavorNutritionalInfo
    tab = True
    extra = 0


class AdditionalNutrientInline(TabularInline):
    model = AdditionalNutrient
    extra = 0


class ProductPriceHistoryInline(TabularInline):
    model = ProductPriceHistory
    tab = True
    extra = 0


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    prepopulated_fields = {"display_name": ("name",)}
    list_per_page = 50


@admin.register(Store)
class StoreAdmin(ModelAdmin):
    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    prepopulated_fields = {"display_name": ("name",)}
    list_per_page = 50


@admin.register(Flavor)
class FlavorAdmin(ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)
    list_per_page = 50


@admin.register(Tag)
class TagAdmin(TreeAdmin, ModelAdmin):
    form = movenodeform_factory(Tag)
    list_display = ("indented_title", "description")
    list_display_links = ("indented_title",)
    search_fields = ("name",)
    list_per_page = 50
    list_filter = ("name",)

    def indented_title(self, obj):
        depth = obj.get_depth() - 1
        return format_html(
            '<div style="padding-left:{}px">{}</div>', depth * 20, obj.name
        )

    indented_title.short_description = "Tag Name"


@admin.register(Category)
class CategoryAdmin(TreeAdmin, ModelAdmin):
    form = movenodeform_factory(Category)
    list_display = ("indented_title", "description")
    list_display_links = ("indented_title",)
    search_fields = ("name",)
    list_per_page = 50

    def indented_title(self, obj):
        depth = obj.get_depth() - 1
        return format_html(
            '<div style="padding-left:{}px">{}</div>', depth * 20, obj.name
        )

    indented_title.short_description = "Category Name"


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("name", "brand", "weight", "packaging", "get_category")
    list_filter = ("brand", "packaging", "category", "tags")
    search_fields = ("name", "brand__name")
    autocomplete_fields = ["brand", "tags", "category"]
    inlines = [ProductStoreInline, ProductFlavorNutritionalInfoInline]
    list_per_page = 50
    filter_horizontal = ["tags"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("brand", "category")
            .prefetch_related("tags", "stores", "flavors")
        )

    def get_category(self, obj):
        return obj.category.name if obj.category else "-"

    get_category.short_description = "Category"


@admin.register(ProductStore)
class ProductStoreAdmin(ModelAdmin):
    list_display = ("product", "store", "external_id", "product_link", "affiliate_link")
    list_filter = ("store",)
    search_fields = ("product__name", "store__name", "external_id")
    autocomplete_fields = ["product", "store"]
    list_per_page = 50
    inlines = [ProductPriceHistoryInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "store")


@admin.register(ProductPriceHistory)
class ProductPriceHistoryAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("get_product", "get_store", "price", "stock_status", "collected_at")
    list_filter = ("stock_status", "store_product_link__store", "collected_at")
    search_fields = (
        "store_product_link__product__name",
        "store_product_link__store__name",
    )
    ordering = ("-collected_at",)
    date_hierarchy = "collected_at"
    list_per_page = 50
    autocomplete_fields = ["store_product_link"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("store_product_link__product", "store_product_link__store")
        )

    def get_product(self, obj):
        return obj.store_product_link.product.name

    get_product.short_description = "Product"

    def get_store(self, obj):
        return obj.store_product_link.store.name

    get_store.short_description = "Store"


@admin.register(NutritionalInfo)
class NutritionalInfoAdmin(ModelAdmin):
    list_display = (
        "product",
        "serving_size_grams",
        "energy_kcal",
        "proteins",
        "carbohydrates",
    )
    search_fields = ("product__name",)
    list_filter = ("product__brand",)
    inlines = [AdditionalNutrientInline]
    list_per_page = 50
    autocomplete_fields = ["product"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product")


@admin.register(ProductFlavorNutritionalInfo)
class ProductFlavorNutritionalInfoAdmin(ModelAdmin):
    list_display = ("product", "flavor", "nutritional_profile")
    search_fields = ("product__name", "flavor__name")
    list_filter = ("flavor", "product__brand")
    autocomplete_fields = ["product", "flavor", "nutritional_profile"]
    list_per_page = 50

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("product", "flavor", "nutritional_profile")
        )
