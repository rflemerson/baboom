from django.contrib import admin
import nested_admin
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
    ProductNutritionProfile,
)


class AdditionalNutrientInline(nested_admin.NestedTabularInline):
    model = AdditionalNutrient
    extra = 0


class NutritionalInfoInline(nested_admin.NestedStackedInline):
    model = NutritionalInfo
    inlines = [AdditionalNutrientInline]
    extra = 1
    min_num = 1
    max_num = 1
    validate_min = True
    validate_max = True


class ProductNutritionProfileInline(nested_admin.NestedStackedInline):
    model = ProductNutritionProfile
    inlines = [NutritionalInfoInline]
    filter_horizontal = ["flavors"]
    extra = 0
    min_num = 1
    validate_min = True


class ProductPriceHistoryInline(nested_admin.NestedTabularInline):
    model = ProductPriceHistory
    extra = 0
    min_num = 1
    validate_min = True
    readonly_fields = ["collected_at"]
    fields = ("price", "stock_status", "collected_at")


class ProductStoreInline(nested_admin.NestedTabularInline):
    model = ProductStore
    extra = 0
    inlines = [ProductPriceHistoryInline]
    min_num = 1
    validate_min = True
    readonly_fields = ["latest_price_info"]
    fields = (
        "store",
        "product_link",
        "affiliate_link",
        "external_id",
        "latest_price_info",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("productpricehistory_set")

    def latest_price_info(self, obj):
        latest_price = obj.productpricehistory_set.order_by("-collected_at").first()
        if latest_price:
            return f"R$ {latest_price.price} ({latest_price.get_stock_status_display()}) em {latest_price.collected_at.strftime('%d/%m/%Y')}"
        return "Nenhum preço registrado ainda."

    latest_price_info.short_description = "Último Preço Registrado"


@admin.register(Product)
class ProductAdmin(nested_admin.NestedModelAdmin):
    list_display = ("name", "brand", "weight", "packaging", "get_category")
    list_filter = ("brand", "packaging", "category", "tags")
    search_fields = ("name", "brand__name")
    autocomplete_fields = ["brand", "tags", "category"]
    inlines = [ProductStoreInline, ProductNutritionProfileInline]
    list_per_page = 50
    filter_horizontal = ["tags"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("brand", "category")
            .prefetch_related(
                "tags", "productnutritionprofile_set__nutritionalinfo_set"
            )
        )

    def get_category(self, obj):
        return obj.category.name if obj.category else "-"

    get_category.short_description = "Category"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    prepopulated_fields = {"display_name": ("name",)}
    list_per_page = 50


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name")
    search_fields = ("name", "display_name")
    prepopulated_fields = {"display_name": ("name",)}
    list_per_page = 50


@admin.register(Flavor)
class FlavorAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)
    list_per_page = 50


@admin.register(Tag)
class TagAdmin(TreeAdmin):
    form = movenodeform_factory(Tag)
    list_display = ("name", "description")
    search_fields = ("name",)
    list_per_page = 50


@admin.register(Category)
class CategoryAdmin(TreeAdmin):
    form = movenodeform_factory(Category)
    list_display = ("name", "description")
    search_fields = ("name",)
    list_per_page = 50


class FullProductPriceHistoryInline(admin.TabularInline):
    model = ProductPriceHistory
    extra = 0
    readonly_fields = ["collected_at"]


@admin.register(ProductStore)
class ProductStoreAdmin(admin.ModelAdmin):
    list_display = ("product", "store", "external_id", "product_link", "affiliate_link")
    list_filter = ("store",)
    search_fields = ("product__name", "store__name", "external_id")
    autocomplete_fields = ["product", "store"]
    inlines = [FullProductPriceHistoryInline]
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "store")


@admin.register(ProductPriceHistory)
class ProductPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("store_product_link", "price", "stock_status", "collected_at")
    list_filter = ("stock_status", "collected_at", "store_product_link__store")
    search_fields = (
        "store_product_link__product__name",
        "store_product_link__store__name",
    )
    autocomplete_fields = ["store_product_link"]
    readonly_fields = ["collected_at"]
    list_per_page = 50

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("store_product_link__product", "store_product_link__store")
        )
