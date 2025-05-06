from django.contrib import admin
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
    ProductNutritionProfile,
)


class ProductStoreInline(admin.TabularInline):
    model = ProductStore
    extra = 0


class ProductNutritionProfileInline(admin.StackedInline):
    model = ProductNutritionProfile
    extra = 1
    filter_horizontal = ["flavors"]
    autocomplete_fields = ["nutritional_info"]


class AdditionalNutrientInline(admin.TabularInline):
    model = AdditionalNutrient
    extra = 0


class ProductPriceHistoryInline(admin.TabularInline):
    model = ProductPriceHistory
    extra = 0


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


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
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
            .prefetch_related("tags", "nutrition_profiles")
        )

    def get_category(self, obj):
        return obj.category.name if obj.category else "-"

    get_category.short_description = "Category"


@admin.register(ProductStore)
class ProductStoreAdmin(admin.ModelAdmin):
    list_display = ("product", "store", "external_id", "product_link", "affiliate_link")
    list_filter = ("store",)
    search_fields = ("product__name", "store__name", "external_id")
    autocomplete_fields = ["product", "store"]
    inlines = [ProductPriceHistoryInline]
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "store")


@admin.register(NutritionalInfo)
class NutritionalInfoAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "serving_size_grams",
        "energy_kcal",
        "proteins",
        "carbohydrates",
    )
    search_fields = ("description",)
    inlines = [AdditionalNutrientInline]
    list_per_page = 50


@admin.register(ProductNutritionProfile)
class ProductNutritionProfileAdmin(admin.ModelAdmin):
    list_display = ("product", "get_flavors", "nutritional_info")
    list_filter = ("product__brand",)
    search_fields = ("product__name", "nutritional_info__description")
    autocomplete_fields = ["product", "nutritional_info"]
    filter_horizontal = ["flavors"]
    list_per_page = 50

    def get_flavors(self, obj):
        return ", ".join([flavor.name for flavor in obj.flavors.all()[:3]])

    get_flavors.short_description = "Flavors"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("product", "nutritional_info")
            .prefetch_related("flavors")
        )
