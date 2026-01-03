from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .filters import ProductFilter
from .forms import AlertSubscriptionForm
from .models import Product

DEFAULT_PER_PAGE = 12
PER_PAGE_OPTIONS = [12, 24, 48]


def product_list(request: HttpRequest) -> HttpResponse:
    products_qs = Product.objects.with_stats()
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

    template = (
        "core/partials/product_list_results.html"
        if getattr(request, "htmx", False)
        else "core/product_list.html"
    )
    return render(request, template, context)


def subscribe_alerts(request: HttpRequest) -> HttpResponse:
    is_htmx = getattr(request, "htmx", False)

    if request.method == "GET" and is_htmx:
        return render(
            request, "core/partials/alerts/form.html", {"form": AlertSubscriptionForm()}
        )

    if request.method == "POST":
        form = AlertSubscriptionForm(request.POST)

        if form.is_valid():
            form.save()
            if is_htmx:
                return render(
                    request,
                    "core/partials/alerts/success.html",
                    {"email": form.cleaned_data["email"]},
                )
            messages.success(
                request, _("You're subscribed! We'll notify you when prices drop.")
            )
        else:
            # Check for duplicate error code using as_data() for robustness
            email_errors = form.errors.as_data().get("email", [])
            is_duplicate = any(e.code == "unique" for e in email_errors)

            if is_htmx:
                if is_duplicate:
                    return render(
                        request,
                        "core/partials/alerts/duplicate.html",
                        {"email": request.POST.get("email")},
                    )

                # Add error class to widget for rendering
                form.fields["email"].widget.attrs["class"] += " input-error"
                # Use the first error message for display
                error_msg = (
                    email_errors[0].message if email_errors else _("Invalid input.")
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
