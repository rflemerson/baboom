"""Shared helpers for core tests."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, cast

from django.core.exceptions import ValidationError

from core.models import Product, ProductStore, Store
from core.units import to_canonical
from offers.models import Offer, PriceObservation, StockStatus

if TYPE_CHECKING:
    from collections.abc import Callable


def _validation_error(operation: Callable[[], object]) -> ValidationError:
    """Return the validation error raised by a catalog write."""
    try:
        operation()
    except ValidationError as error:
        return error
    message = "Expected the operation to raise a ValidationError."
    raise AssertionError(message)


def _grams(value: object) -> Decimal:
    """Return a mass stated in grams in the unit the models store."""
    return to_canonical(Decimal(str(value)), "g")


def _per_gram(value: Decimal) -> Decimal:
    """Return a per-canonical-mass metric restated per gram."""
    return value * to_canonical(Decimal(1), "g")


def _link_offer(
    **kwargs: object,
) -> ProductStore:
    """Create an offer-backed store listing for tests.

    Mirrors the production model: the price series lives on the merchant offer,
    while ProductStore only links the product to that offer.
    """
    product = cast("Product", kwargs["product"])
    store = cast("Store", kwargs["store"])
    external_id = cast("str | None", kwargs.get("external_id"))
    product_link = cast("str", kwargs.get("product_link", ""))
    price = cast("float | Decimal | None", kwargs.get("price"))
    stock_status = cast("str", kwargs.get("stock_status", StockStatus.AVAILABLE))
    resolved_external_id = (
        external_id if external_id is not None else f"{store.name}-{product.pk}"
    )
    resolved_price = Decimal(str(price)) if price is not None else None
    offer = Offer.objects.create(
        store_slug=store.name,
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
    return ProductStore.objects.create(product=product, store=store, offer=offer)


class CatalogAnnotatedProduct(Protocol):
    """Typed surface for selector rows with catalog annotations."""

    concentration: Decimal | None
    total_active: Decimal | None
    price_per_active: Decimal | None
    external_link: str | None
    last_price: Decimal | None
