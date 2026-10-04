"""Shared helpers for core tests."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, cast

from django.core.exceptions import ValidationError
from django.utils import timezone

from commerce.services import CommerceIdentityService, MarketRef, SellerRef
from core.models import Product, ProductStore, Store
from core.selectors import (
    PriceSource,
    public_catalog_products,
    public_catalog_products_with_stats,
)
from offers.models import Offer, PriceObservation, StockStatus
from pricing.projections import ProjectionService
from pricing.selectors import projected_prices, public_policy

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import QuerySet

    from commerce.models import SellerAccount
    from core.dtos import CatalogProductsFilters


def _validation_error(operation: Callable[[], object]) -> ValidationError:
    """Return the validation error raised by a catalog write."""
    try:
        operation()
    except ValidationError as error:
        return error
    message = "Expected the operation to raise a ValidationError."
    raise AssertionError(message)


def store_seller(slug: str) -> SellerAccount:
    """Return the Brazilian store's own seller, as a crawl records it."""
    market = CommerceIdentityService.market(
        MarketRef(
            namespace=slug,
            channel_name=slug,
            channel_kind="independent_store",
            adapter="shopify",
            country="BR",
            currency="BRL",
            timezone="America/Sao_Paulo",
        ),
    )
    return CommerceIdentityService.seller(market, SellerRef(is_channel_owner=True))


def _link_offer(
    **kwargs: object,
) -> ProductStore:
    """Create an offer-backed store listing for tests.

    Mirrors the production model: the price series lives on the merchant offer,
    while ProductStore only links a catalog row to that offer. A simple product
    links the product; its flavor rules live on the model.
    """
    product = cast("Product", kwargs["product"])
    store = cast("Store", kwargs["store"])
    external_id = cast("str | None", kwargs.get("external_id"))
    product_link = cast("str", kwargs.get("product_link", ""))
    price = cast("float | Decimal | None", kwargs.get("price"))
    stock_status = cast("str", kwargs.get("stock_status", StockStatus.AVAILABLE))
    resolved_external_id = (
        external_id if external_id is not None else f"{store.scraper_slug}-{product.pk}"
    )
    resolved_price = Decimal(str(price)) if price is not None else None
    offer = Offer.objects.create(
        seller_account=store_seller(store.scraper_slug),
        store_slug=store.scraper_slug,
        external_id=resolved_external_id,
        url=product_link,
        current_price=resolved_price,
        current_stock_status=stock_status,
    )
    if resolved_price is not None:
        PriceObservation.objects.create(
            offer=offer,
            price=resolved_price,
            stock_status=stock_status,
        )
    return ProductStore.objects.create(
        product=product,
        offer=offer,
    )


class CatalogAnnotatedProduct(Protocol):
    """Typed surface for selector rows with catalog annotations."""

    concentration: Decimal | None
    total_active: Decimal | None
    price_per_active: Decimal | None
    external_link: str | None
    price: Decimal | None


def _raised(operation: Callable[[], object], expected: type[Exception]) -> Exception:
    """Return the exception an operation is expected to raise."""
    try:
        operation()
    except expected as error:
        return error
    message = f"Expected the operation to raise {expected.__name__}."
    raise AssertionError(message)


def projected_catalog(
    filters: CatalogProductsFilters | None = None,
) -> QuerySet[Product]:
    """Project every offer under the default policy and return the catalog."""
    ProjectionService().refresh()
    return public_catalog_products(_default_prices(), filters)


def projected_catalog_with_stats(active_slug: str | None = None) -> QuerySet[Product]:
    """Project every offer and return the annotated catalog, unfiltered."""
    ProjectionService().refresh()
    return public_catalog_products_with_stats(_default_prices(), active_slug)


def _default_prices() -> PriceSource:
    policy = public_policy()
    assert policy is not None
    return projected_prices(policy, timezone.now(), country="BR", currency="BRL")
