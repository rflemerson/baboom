"""Public REST views consumed by the frontend."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from baboom.utils import format_graphql_errors
from core.dtos import CatalogProductsFilters
from core.selectors import public_catalog_products
from core.services import AlertSubscriptionService

if TYPE_CHECKING:
    from decimal import Decimal

    from core.models import Product

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
        price_min=_optional_float(query_params.get("price_min")),
        price_max=_optional_float(query_params.get("price_max")),
        price_per_protein_gram_min=_optional_float(
            query_params.get("price_per_protein_gram_min"),
        ),
        price_per_protein_gram_max=_optional_float(
            query_params.get("price_per_protein_gram_max"),
        ),
        concentration_min=_optional_float(query_params.get("concentration_min")),
        concentration_max=_optional_float(query_params.get("concentration_max")),
        sort_by=query_params.get("sort_by", "price_per_protein_gram"),
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
    """Serialize nullable Decimal annotations like GraphQL does."""
    if value is None:
        return None
    return str(value)


def _serialize_catalog_product(product: Product) -> dict[str, Any]:
    """Serialize the public catalog product shape used by the frontend."""
    return {
        "id": product.pk,
        "name": product.name,
        "packagingDisplay": product.get_packaging_display(),
        "weight": product.weight,
        "lastPrice": _decimal_to_str(product.last_price),
        "pricePerProteinGram": _decimal_to_str(product.price_per_protein_gram),
        "concentration": _decimal_to_str(product.concentration),
        "totalProtein": _decimal_to_str(product.total_protein),
        "externalLink": product.external_link,
        "brand": {"name": product.brand.name},
        "category": {"name": product.category.name} if product.category else None,
        "tags": [{"name": tag.name} for tag in product.tags.all()],
    }


def _apply_catalog_cache_headers(response: JsonResponse) -> JsonResponse:
    """Tell browsers and Cloudflare how long public catalog data can be cached."""
    browser_ttl = max(int(settings.CATALOG_PRODUCTS_BROWSER_CACHE_SECONDS), 0)
    edge_ttl = max(int(settings.CATALOG_PRODUCTS_EDGE_CACHE_SECONDS), 0)
    response["Cache-Control"] = (
        f"public, max-age={browser_ttl}, s-maxage={edge_ttl}, "
        "stale-while-revalidate=86400"
    )
    return response


@require_GET
def catalog_products(request: HttpRequest) -> JsonResponse | HttpResponseBadRequest:
    """Return cacheable public catalog products for the frontend."""
    try:
        query_filters = _catalog_filters_from_request(request)
        page, per_page = _catalog_page_params(request)
    except ValueError:
        return HttpResponseBadRequest("Invalid catalog query parameter.")

    queryset = public_catalog_products(query_filters)
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page)
    response = JsonResponse(
        {
            "pageInfo": {
                "currentPage": page_obj.number,
                "perPage": per_page,
                "totalPages": paginator.num_pages,
                "totalCount": paginator.count,
                "hasPreviousPage": page_obj.has_previous(),
                "hasNextPage": page_obj.has_next(),
            },
            "items": [
                _serialize_catalog_product(product) for product in page_obj.object_list
            ],
        },
    )
    return _apply_catalog_cache_headers(response)


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
                    {"field": item.field, "message": item.message}
                    for item in format_graphql_errors(error)
                ],
            },
            status=400,
        )
