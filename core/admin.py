import nested_admin
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import (
    Brand,
    Category,
    Flavor,
    Micronutrient,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
    Tag,
)


class MicronutrientInline(nested_admin.NestedTabularInline):
    model = Micronutrient
    extra = 0
    min_num = 0
    classes = ["collapse"]


class ProductNutritionInline(nested_admin.NestedTabularInline):
    model = ProductNutrition
    extra = 0
    autocomplete_fields = ["nutrition_facts"]
    filter_horizontal = ["flavors"]
    classes = ["collapse"]


class ProductPriceHistoryInline(nested_admin.NestedTabularInline):
    model = ProductPriceHistory
    extra = 0
    readonly_fields = ["collected_at"]
    fields = ("price", "stock_status", "collected_at")
    ordering = ("-collected_at",)
    max_num = 5


class ProductStoreInline(nested_admin.NestedTabularInline):
    model = ProductStore
    inlines = [ProductPriceHistoryInline]
    extra = 0
    min_num = 1
    fields = (
        "store",
        "external_id",
        "product_link",
        "affiliate_link",
    )


@admin.register(Product)
class ProductAdmin(nested_admin.NestedModelAdmin):
    show_facets = admin.ShowFacets.ALWAYS
    list_display = (
        "name",
        "brand",
        "weight",
        "packaging",
        "get_category",
        "created_at",
    )
    list_filter = ("brand", "packaging", "category", "tags")
    search_fields = ("name", "brand__name")
    autocomplete_fields = ["brand", "tags", "category"]
    inlines = [ProductStoreInline, ProductNutritionInline]
    list_per_page = 20
    filter_horizontal = ["tags"]
    save_on_top = True

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .select_related("brand", "category")
            .prefetch_related("tags")
        )

    @admin.display(description="Categoria", ordering="category__name")
    def get_category(self, obj: Product) -> str:
        return obj.category.name if obj.category else "-"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    show_facets = admin.ShowFacets.ALWAYS
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


@admin.register(ProductStore)
class ProductStoreAdmin(admin.ModelAdmin):
    show_facets = admin.ShowFacets.ALWAYS
    list_display = ("product", "store", "external_id", "get_last_price")
    list_filter = ("store",)
    search_fields = ("product__name", "store__name", "external_id")
    autocomplete_fields = ["product", "store"]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .select_related("product", "store")
            .prefetch_related("price_history")
        )

    @admin.display(description="Último Preço")
    def get_last_price(self, obj: ProductStore) -> str:
        last = obj.price_history.first()
        return f"R$ {last.price}" if last else "-"


@admin.register(ProductPriceHistory)
class ProductPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("store_product_link", "price", "stock_status", "collected_at")
    list_filter = ("stock_status", "collected_at", "store_product_link__store")
    autocomplete_fields = ["store_product_link"]
    readonly_fields = ["collected_at"]


@admin.register(NutritionFacts)
class NutritionFactsAdmin(nested_admin.NestedModelAdmin):
    list_display = ("description", "serving_size_grams", "energy_kcal")
    search_fields = ("description",)
    inlines = [MicronutrientInline]
    list_per_page = 20
