from unfold.admin import ModelAdmin, TabularInline
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import (
    Brand,
    Store,
    Flavor,
    TagCategory,
    Tag,
    Product,
    ProductStore,
    ProductPriceHistory,
    NutritionalInfo,
    AdditionalNutrient,
    ProductFlavorNutritionalInfo,
)


class ProductStoreInline(TabularInline):
    model = ProductStore
    extra = 0
    verbose_name = "Store Link"
    verbose_name_plural = "Store Links"
    autocomplete_fields = ["store"]
    ordering_field = None


class ProductFlavorNutritionalInfoInline(TabularInline):
    model = ProductFlavorNutritionalInfo
    extra = 0
    verbose_name = "Flavor-Nutrition Combination"
    verbose_name_plural = "Flavor-Nutrition Combinations"
    autocomplete_fields = ["flavor", "nutritional_info"]
    ordering_field = None


class AdditionalNutrientInline(TabularInline):
    model = AdditionalNutrient
    extra = 0
    verbose_name = "Additional Nutrient"
    verbose_name_plural = "Additional Nutrients"
    ordering_field = None


class ProductPriceHistoryInline(TabularInline):
    model = ProductPriceHistory
    extra = 0
    verbose_name = "Price and Stock History"
    verbose_name_plural = "Price and Stock History"
    ordering_field = None
    fields = ["price", "stock_status", "collected_at"]
    readonly_fields = ["collected_at"]
    max_num = 10
    ordering = ["-collected_at"]


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


@admin.register(TagCategory)
class TagCategoryAdmin(ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)
    list_per_page = 50


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ("name", "category", "description")
    list_filter = ("category",)
    search_fields = ("name", "category__name")
    list_per_page = 50
    autocomplete_fields = ["category"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("category")


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("name", "brand", "weight", "packaging")
    list_filter = ("brand", "packaging", "tags")
    search_fields = ("name", "brand__name")
    autocomplete_fields = ["brand", "tags"]
    inlines = [ProductStoreInline, ProductFlavorNutritionalInfoInline]
    list_per_page = 50
    filter_horizontal = ["tags"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("brand")
            .prefetch_related("tags")
        )


@admin.register(ProductStore)
class ProductStoreAdmin(ModelAdmin):
    list_display = ("product", "store", "affiliate_link", "product_link")
    list_filter = ("store",)
    search_fields = ("product__name", "store__name")
    autocomplete_fields = ["product", "store"]
    list_per_page = 50
    inlines = [ProductPriceHistoryInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "store")


# Simple fix: Change inheritance order to prioritize Unfold's ModelAdmin
@admin.register(ProductPriceHistory)
class ProductPriceHistoryAdmin(ModelAdmin, SimpleHistoryAdmin):  # Changed order
    list_display = ("store_link", "price", "stock_status", "collected_at")
    list_filter = ("stock_status", "store_link__store", "collected_at")
    search_fields = ("store_link__product__name", "store_link__store__name")
    ordering = ("-collected_at",)
    history_list_display = ["price", "stock_status"]
    date_hierarchy = "collected_at"
    list_per_page = 50
    autocomplete_fields = ["store_link"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("store_link__product", "store_link__store")
        )


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
    list_display = ("product", "flavor", "nutritional_info")
    search_fields = ("product__name", "flavor__name")
    list_filter = ("flavor", "product__brand")
    autocomplete_fields = ["product", "flavor", "nutritional_info"]
    list_per_page = 50

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("product", "flavor", "nutritional_info")
        )
