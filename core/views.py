from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .filters import ProductFilter
from .models import AlertSubscriber, Product

DEFAULT_PER_PAGE = 12
PER_PAGE_OPTIONS = [12, 24, 48]


def product_list(request: HttpRequest) -> HttpResponse:
    products_qs = Product.objects.with_stats()
    product_filter = ProductFilter(request.GET, queryset=products_qs)

    # Get items per page from request, validate against allowed options
    try:
        per_page = int(request.GET.get("per_page", DEFAULT_PER_PAGE))
        if per_page not in PER_PAGE_OPTIONS:
            per_page = DEFAULT_PER_PAGE
    except (ValueError, TypeError):
        per_page = DEFAULT_PER_PAGE

    paginator = Paginator(product_filter.qs, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "filter": product_filter,
        "products": page_obj,
        "page_obj": page_obj,
        "per_page": per_page,
    }

    if getattr(request, "htmx", False):
        template_name = "core/partials/product_list_results.html"
    else:
        template_name = "core/product_list.html"

    return render(request, template_name, context)


def subscribe_alerts(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        # HTMX handling
        if getattr(request, "htmx", False):
            # 1. Validate existence
            if not email:
                return render(
                    request,
                    "core/partials/alerts/form.html",
                    {"error": _("Please enter an email address.")},
                )

            # 2. Validate format
            try:
                validate_email(email)
            except ValidationError:
                return render(
                    request,
                    "core/partials/alerts/form.html",
                    {"error": _("Invalid email format."), "email": email},
                )

            # 3. Create subscription
            try:
                AlertSubscriber.objects.create(email=email)
                return render(
                    request, "core/partials/alerts/success.html", {"email": email}
                )
            except IntegrityError:
                return render(
                    request, "core/partials/alerts/duplicate.html", {"email": email}
                )

        # Fallback for non-HTMX requests (old behavior)
        if email:
            try:
                validate_email(email)
                AlertSubscriber.objects.create(email=email)
                messages.success(
                    request, _("You're subscribed! We'll notify you when prices drop.")
                )
            except ValidationError:
                messages.error(request, _("Invalid email format."))
            except IntegrityError:
                messages.info(request, _("This email is already subscribed."))
        else:
            messages.error(request, _("Please enter a valid email."))

    # If it's a GET request via HTMX (e.g. "Use another email" button), return fresh form
    if request.method == "GET" and getattr(request, "htmx", False):
        return render(request, "core/partials/alerts/form.html")

    return redirect("product_list")
