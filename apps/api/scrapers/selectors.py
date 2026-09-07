"""Read-only selectors for the local product-review workflow."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from core.models import Brand, Category, Product, Tag

from .models import ScrapedItem, ScrapedItemExtraction


def review_items(
    *,
    status: str | None = ScrapedItem.Status.QUEUED,
    search: str = "",
    limit: int = 20,
) -> QuerySet[ScrapedItem]:
    """Return a bounded review queue without reserving any item."""
    queryset = ScrapedItem.objects.select_related("offer", "source_page").order_by(
        "updated_at",
        "id",
    )
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(
            Q(offer__name__icontains=search)
            | Q(offer__external_id__icontains=search)
            | Q(offer__ean__icontains=search)
            | Q(offer__store_slug__icontains=search),
        )
    return queryset[: max(1, min(limit, 100))]


def review_item(item_id: int) -> ScrapedItem | None:
    """Return one review item by stable id without changing its state."""
    return (
        ScrapedItem.objects.select_related("offer", "source_page")
        .filter(id=item_id)
        .first()
    )


def review_extraction(item_id: int) -> ScrapedItemExtraction | None:
    """Return the staged extraction for a review item, when present."""
    return (
        ScrapedItemExtraction.objects.select_related("scraped_item", "source_page")
        .filter(scraped_item_id=item_id)
        .first()
    )


def catalog_candidates(
    *,
    search: str = "",
    ean: str = "",
    limit: int = 20,
) -> QuerySet[Product]:
    """Search published and unpublished products for duplicate resolution."""
    queryset = Product.objects.select_related("brand", "category").order_by(
        "brand__name",
        "name",
        "id",
    )
    if ean:
        queryset = queryset.filter(ean=ean)
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(brand__name__icontains=search)
            | Q(brand__display_name__icontains=search)
            | Q(ean__icontains=search),
        )
    return queryset[: max(1, min(limit, 100))]


def catalog_brands(search: str = "", limit: int = 50) -> QuerySet[Brand]:
    """Return brand choices available to product approval."""
    queryset = Brand.objects.order_by("name", "id")
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(display_name__icontains=search),
        )
    return queryset[: max(1, min(limit, 100))]


def catalog_categories(search: str = "", limit: int = 50) -> QuerySet[Category]:
    """Return category choices available to product approval."""
    queryset = Category.objects.order_by("path", "id")
    if search:
        queryset = queryset.filter(name__icontains=search)
    return queryset[: max(1, min(limit, 100))]


def catalog_tags(search: str = "", limit: int = 50) -> QuerySet[Tag]:
    """Return tag choices available to product approval."""
    queryset = Tag.objects.order_by("path", "id")
    if search:
        queryset = queryset.filter(name__icontains=search)
    return queryset[: max(1, min(limit, 100))]
