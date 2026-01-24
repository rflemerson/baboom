from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django_htmx.middleware import HtmxDetails  # <--- Importe HtmxDetails

from core.components.list.results.results import ListResults

from .filters import ProductFilter
from .forms import AlertSubscriptionForm
from .selectors import list_with_stats
from .services import alert_subscriber_create

DEFAULT_PER_PAGE = 12
PER_PAGE_OPTIONS = [12, 24, 48]


# --- CORREÇÃO DO MYPY ---
# Definimos uma classe apenas para Tipagem que extende HttpRequest
# e diz ao MyPy que existe um atributo .htmx
class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


# ------------------------


def list_view(request: HtmxHttpRequest) -> HttpResponse:
    products_qs = list_with_stats()
    product_filter = ProductFilter(request.GET, queryset=products_qs)

    try:
        per_page = int(request.GET.get("per_page", DEFAULT_PER_PAGE))
        if per_page not in PER_PAGE_OPTIONS:
            per_page = DEFAULT_PER_PAGE
    except (ValueError, TypeError):
        per_page = DEFAULT_PER_PAGE

    paginator = Paginator(product_filter.qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context_data = {
        "page_obj": page_obj,
        "per_page": per_page,
        "query_params": dict(request.GET),
    }

    if request.htmx:
        html = ListResults.render(kwargs=context_data)
        return HttpResponse(html)

    full_context = {"filter": product_filter, **context_data}

    return render(request, "base.html", full_context)


def subscribe_alerts(request: HttpRequest) -> HttpResponse:
    # Aqui usamos getattr, então HttpRequest padrão funciona sem erro de tipagem
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
            if is_htmx:
                form.fields["email"].widget.attrs["class"] += " input-error"
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

    return redirect("list")
