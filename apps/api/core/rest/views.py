"""Public REST views consumed by the frontend."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.utils.http import http_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from commerce.models import Currency
from core import units
from core.dtos import CatalogProductsFilters
from core.selectors import catalog_active, current_prices, public_catalog_products
from core.services import AlertSubscriptionService
from pricing.selectors import projected_prices, public_policy

if TYPE_CHECKING:
    from datetime import datetime

    from core.models import Product, ProductNutrition

CATALOG_PER_PAGE_CHOICES = {12, 24, 48}
CATALOG_DEFAULT_PER_PAGE = 12


def _optional_str(value: str | None) -> str | None:
    """Normalize empty query string values to null."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _optional_float(value: str | None) -> float | None:
    """Parse optional numeric query params."""
    if value in {None, ""}:
        return None
    return float(value)


def _positive_int(value: str | None, default: int) -> int:
    """Parse positive integer query params with a fallback."""
    if value in {None, ""}:
        return default
    return max(int(value), 1)


def _catalog_filters_from_request(request: HttpRequest) -> CatalogProductsFilters:
    """Map public query string params to the selector DTO."""
    query_params = request.GET
    return CatalogProductsFilters(
        search=_optional_str(query_params.get("search")),
        brand=_optional_str(query_params.get("brand")),
        active=_optional_str(query_params.get("active")),
        price_min=_optional_float(query_params.get("price_min")),
        price_max=_optional_float(query_params.get("price_max")),
        price_per_active_min=_optional_float(
            query_params.get("price_per_active_min"),
        ),
        price_per_active_max=_optional_float(
            query_params.get("price_per_active_max"),
        ),
        concentration_min=_optional_float(query_params.get("concentration_min")),
        concentration_max=_optional_float(query_params.get("concentration_max")),
        sort_by=query_params.get("sort_by", "price_per_active"),
        sort_dir=query_params.get("sort_dir", "asc"),
    )


def _catalog_page_params(request: HttpRequest) -> tuple[int, int]:
    """Return normalized catalog pagination params."""
    page = _positive_int(request.GET.get("page"), 1)
    requested_per_page = _positive_int(
        request.GET.get("per_page"),
        CATALOG_DEFAULT_PER_PAGE,
    )
    per_page = (
        requested_per_page
        if requested_per_page in CATALOG_PER_PAGE_CHOICES
        else CATALOG_DEFAULT_PER_PAGE
    )
    return page, per_page


def _decimal_to_str(value: Decimal | None) -> str | None:
    """Serialize nullable Decimal annotations for the public API."""
    if value is None:
        return None
    return str(value)


def _money_to_str(value: Decimal | None, minor_unit: int) -> str | None:
    """Serialize an amount in its currency's precision: cents, yen, fils."""
    if value is None:
        return None
    return str(Decimal(value).quantize(Decimal(1).scaleb(-minor_unit)))


def _profiles_by_id(products: list[Product]) -> dict[int, ProductNutrition]:
    """Index the prefetched profiles of a page by their own id.

    A product with several labels yields one catalog row per label, and each
    row needs only its own profile, so the page is indexed once instead of
    rescanning every product's profiles for every row.
    """
    return {
        profile.pk: profile
        for product in products
        for profile in product.nutrition_profiles.all()
    }


def _pricing_terms(details: object, currency: Currency) -> dict[str, Any]:
    """Name what the buyer needs to execute the shown price.

    The coupon codes the price requires, the monetary cashback of the same
    alternative (shown apart, never taken off the price) and the route's
    activation instruction.
    """
    found = details if isinstance(details, dict) else {}
    cashback = found.get("cashback")
    routes = found.get("routes") or []
    return {
        "couponCodes": [str(code) for code in found.get("public_codes") or []],
        "cashback": (
            {
                "amount": _money_to_str(Decimal(str(cashback)), currency.minor_unit),
                "currency": currency.code,
            }
            if cashback
            else None
        ),
        "routeInstructions": next(
            (route["instructions"] for route in routes if route.get("instructions")),
            None,
        ),
    }


def _serialize_catalog_product(
    product: Product,
    profiles: dict[int, ProductNutrition],
    currency: Currency,
) -> dict[str, Any]:
    """Serialize the public catalog product shape used by the frontend."""
    profile = profiles.get(product.nutrition_profile_id)
    return {
        "id": product.pk,
        "name": product.name,
        "nutritionProfile": (
            {
                "id": profile.pk,
                "nutritionFactsId": product.nutrition_facts_id,
                "flavors": [flavor.name for flavor in profile.flavors.all()],
            }
            if profile is not None
            else None
        ),
        "packagingDisplay": product.get_packaging_display(),
        "netMass": _decimal_to_str(product.net_mass),
        "price": _money_to_str(product.price, currency.minor_unit),
        "currency": currency.code if product.price is not None else None,
        "pricePerActive": _decimal_to_str(product.price_per_active),
        "concentration": _decimal_to_str(product.concentration),
        "totalActive": _decimal_to_str(product.total_active),
        "externalLink": product.external_link,
        "pricingDetails": product.pricing_details,
        **_pricing_terms(product.pricing_details, currency),
        "comparisonAmount": _money_to_str(
            product.comparison_price,
            currency.minor_unit,
        ),
        "paymentMethod": product.payment_method or None,
        "optimizationStatus": product.price_search_status or None,
        "linkSelectsSeller": product.link_selects_seller,
        "brand": {"name": product.brand.name},
        "category": {"name": product.category.name} if product.category else None,
        "tags": [{"name": tag.name} for tag in product.tags.all()],
    }


def _apply_catalog_cache_headers(
    response: JsonResponse,
    *,
    expires_at: datetime | None,
) -> JsonResponse:
    """Tell browsers and the CDN how long this page of prices may be cached.

    No cache may outlive the earliest expiry of a price on the page. Prices
    follow promotions that can be suspended at any moment, so the edge TTL is
    capped and no stale copy is served while revalidating.
    """
    browser_ttl = max(int(settings.CATALOG_PRODUCTS_BROWSER_CACHE_SECONDS), 0)
    edge_ttl = max(int(settings.CATALOG_PRODUCTS_EDGE_CACHE_SECONDS), 0)
    if expires_at is not None:
        remaining = max(int((expires_at - timezone.now()).total_seconds()), 0)
        browser_ttl, edge_ttl = min(browser_ttl, remaining), min(edge_ttl, remaining)
    response["Cache-Control"] = (
        f"public, max-age={browser_ttl}, s-maxage={edge_ttl}, stale-while-revalidate=0"
    )
    if expires_at is not None:
        response["Expires"] = http_date(expires_at.timestamp())
    return response


def _market_params(request: HttpRequest) -> tuple[str, str]:
    """Return the requested market: a country and the currency it is priced in."""
    country = (_optional_str(request.GET.get("country")) or "").upper()
    currency = (_optional_str(request.GET.get("currency")) or "").upper()
    country = country or settings.CATALOG_DEFAULT_COUNTRY
    currency = currency or settings.CATALOG_DEFAULT_CURRENCY
    if not Currency.objects.filter(code=currency).exists() or len(country) != len("BR"):
        raise ValueError(country, currency)
    return country, currency


@require_GET
def catalog_products(request: HttpRequest) -> JsonResponse | HttpResponseBadRequest:
    """Return cacheable public catalog products for one market."""
    try:
        query_filters = _catalog_filters_from_request(request)
        page, per_page = _catalog_page_params(request)
        country, currency = _market_params(request)
    except ValueError:
        return HttpResponseBadRequest("Invalid catalog query parameter.")

    policy = public_policy(_optional_str(request.GET.get("scenario")))
    if policy is None:
        return HttpResponseBadRequest("Unknown pricing scenario.")
    projected = country in settings.PRICING_PROJECTION_COUNTRIES
    price_source = (
        projected_prices(policy, timezone.now(), country=country, currency=currency)
        if projected
        else current_prices(country, currency)
    )
    queryset = public_catalog_products(price_source, query_filters)
    currency_row = Currency.objects.get(code=currency)
    active = catalog_active(query_filters.active)
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page)
    profiles = _profiles_by_id(page_obj.object_list)
    expiries = [
        product.price_expires_at
        for product in page_obj.object_list
        if product.price_expires_at is not None
    ]
    response = JsonResponse(
        {
            "active": ({"slug": active.slug, "name": active.name} if active else None),
            "massUnit": units.MASS_UNIT,
            "market": {"country": country, "currency": currency},
            "scenario": (
                {"key": policy.key, "version": policy.number}
                if projected
                else {"key": "current", "version": None}
            ),
            "pageInfo": {
                "currentPage": page_obj.number,
                "perPage": per_page,
                "totalPages": paginator.num_pages,
                "totalCount": paginator.count,
                "hasPreviousPage": page_obj.has_previous(),
                "hasNextPage": page_obj.has_next(),
            },
            "items": [
                _serialize_catalog_product(product, profiles, currency_row)
                for product in page_obj.object_list
            ],
        },
    )
    return _apply_catalog_cache_headers(
        response,
        expires_at=min(expiries) if expiries else None,
    )


@csrf_exempt
@require_POST
def subscribe_alerts(request: HttpRequest) -> JsonResponse | HttpResponseBadRequest:
    """Subscribe an email to price alerts from the public frontend."""
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    email = payload.get("email")
    if not isinstance(email, str):
        return HttpResponseBadRequest("Missing email.")

    try:
        result = AlertSubscriptionService().execute(email=email)
        return JsonResponse(
            {
                "success": not result.already_subscribed,
                "alreadySubscribed": result.already_subscribed,
                "email": result.email,
                "errors": None,
            },
        )
    except DjangoValidationError as error:
        return JsonResponse(
            {
                "success": False,
                "alreadySubscribed": False,
                "email": email,
                "errors": [
                    {"field": field, "message": message}
                    for field, messages in (
                        error.message_dict.items()
                        if hasattr(error, "error_dict")
                        else [("non_field_errors", error.messages)]
                    )
                    for message in messages
                ],
            },
            status=400,
        )
