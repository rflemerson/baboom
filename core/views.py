from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
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


def components_playground(request: HttpRequest) -> HttpResponse:
    """
    View for testing and developing components in isolation.
    """
    if not request.user.is_staff and not settings.DEBUG:
        raise Http404

    # Get some sample data for testing
    from .selectors import product_list_with_stats

    sample_product = product_list_with_stats().first()

    # Handle playground message triggers
    msg_type = request.GET.get("msg")
    if msg_type == "success":
        messages.success(request, "Operação realizada com sucesso! (Success)")
    elif msg_type == "error":
        messages.error(request, "Algo deu errado. Tente novamente. (Error)")
    elif msg_type == "info":
        messages.info(request, "Apenas para sua informação. (Info)")
    elif msg_type == "warning":
        messages.warning(request, "Atenção: verifique os dados. (Warning)")

    # We don't need to pass 'messages' manually if it's in context_processors,
    # BUT component expects 'alert_messages'.
    # We can retrieve it from storage or rely on context processor if we render with RequestContext.
    # The render() function does use RequestContext.
    # So 'messages' will be available in the template.

    # Instantiate filter for QuickFilters component
    from .filters import ProductFilter

    queryset = product_list_with_stats()
    product_filter = ProductFilter(request.GET, queryset=queryset)

    # Pagination Logic
    DEFAULT_PER_PAGE = 12
    PER_PAGE_OPTIONS = [12, 24, 48]
    try:
        per_page = int(request.GET.get("per_page", DEFAULT_PER_PAGE))
        if per_page not in PER_PAGE_OPTIONS:
            per_page = DEFAULT_PER_PAGE
    except (ValueError, TypeError):
        per_page = DEFAULT_PER_PAGE

    paginator = Paginator(product_filter.qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "product": sample_product,
        "filter": product_filter,
        "page_obj": page_obj,
        "per_page": per_page,
    }
    return render(request, "core/playground.html", context)
