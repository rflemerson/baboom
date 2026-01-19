from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .filters import ProductFilter
from .forms import AlertSubscriptionForm
from .selectors import product_list_with_stats
from .services import alert_subscriber_create

DEFAULT_PER_PAGE = 12
PER_PAGE_OPTIONS = [12, 24, 48]


def product_list(request: HttpRequest) -> HttpResponse:
    products_qs = product_list_with_stats()
    product_filter = ProductFilter(request.GET, queryset=products_qs)

    try:
        per_page = int(request.GET.get("per_page", DEFAULT_PER_PAGE))
        if per_page not in PER_PAGE_OPTIONS:
            per_page = DEFAULT_PER_PAGE
    except (ValueError, TypeError):
        per_page = DEFAULT_PER_PAGE

    paginator = Paginator(product_filter.qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "filter": product_filter,
        "products": page_obj,
        "page_obj": page_obj,
        "per_page": per_page,
    }

    return render(request, "base.html", context)


def subscribe_alerts(request: HttpRequest) -> HttpResponse:
    is_htmx = getattr(request, "htmx", False)

    if request.method == "GET" and is_htmx:
        return render(
            request, "core/partials/alerts/form.html", {"form": AlertSubscriptionForm()}
        )

    if request.method == "POST":
        form = AlertSubscriptionForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                alert_subscriber_create(email=email)
                if is_htmx:
                    return render(
                        request,
                        "core/partials/alerts/success.html",
                        {"email": email},
                    )
                messages.success(
                    request, _("You're subscribed! We'll notify you when prices drop.")
                )
            except ValidationError as e:
                # Handle service-level validation errors (e.g. unique constraint)
                if hasattr(e, "code") and e.code == "unique":
                    if is_htmx:
                        return render(
                            request,
                            "core/partials/alerts/duplicate.html",
                            {"email": email},
                        )
                    messages.error(request, e.message)
                else:
                    messages.error(request, str(e))
        else:
            # Handle form-level validation errors
            if is_htmx:
                # Add error class to widget for rendering
                form.fields["email"].widget.attrs["class"] += " input-error"
                # Use the first error message for display
                error_msg = (
                    form.errors["email"][0]
                    if "email" in form.errors
                    else _("Invalid input.")
                )
                return render(
                    request,
                    "core/partials/alerts/form.html",
                    {"error": error_msg, "form": form},
                )

            for field_errors in form.errors.values():
                for err in field_errors:
                    messages.error(request, str(err))

    return redirect("product_list")
