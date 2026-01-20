import django_filters
from django import forms
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from .models import Product


class ProductFilter(django_filters.FilterSet):
    SORT_CHOICES = (
        ("price_per_gram", _("Price/g")),
        ("last_price", _("Price")),
        ("total_protein", _("Protein")),
        ("concentration", _("Concentration")),
    )
    SORT_DIR_CHOICES = (
        ("asc", _("Low to High")),
        ("desc", _("High to Low")),
    )
    VALID_SORT_FIELDS = {key for key, _ in SORT_CHOICES}

    @property
    def sort_choices(self) -> list[tuple[str, str, bool]]:
        """Return sort choices with selected state."""
        current = self.data.get("sort_by", "price_per_gram")
        return [(key, str(label), key == current) for key, label in self.SORT_CHOICES]

    @property
    def current_sort_label(self) -> str:
        """Return the label of the currently selected sort field."""
        return str(dict(self.SORT_CHOICES).get(self.current_sort_key, _("Price/g")))

    @property
    def current_sort_key(self) -> str:
        """Return the current sort key with default fallback."""
        return self.data.get("sort_by", "price_per_gram")

    @property
    def current_sort_dir(self) -> str:
        """Return the current sort direction."""
        return self.data.get("sort_dir", "asc")

    search = django_filters.CharFilter(
        method="filter_search",
        label=_("Search"),
        widget=forms.TextInput(attrs={"placeholder": _("Search...")}),
    )

    price_min = django_filters.NumberFilter(
        field_name="last_price",
        lookup_expr="gte",
        label=_("Min Price"),
        widget=forms.NumberInput(attrs={"placeholder": _("Min")}),
    )
    price_max = django_filters.NumberFilter(
        field_name="last_price",
        lookup_expr="lte",
        label=_("Max Price"),
        widget=forms.NumberInput(attrs={"placeholder": _("Max")}),
    )
    price_per_gram_min = django_filters.NumberFilter(
        field_name="price_per_gram",
        lookup_expr="gte",
        label=_("Min Price/g"),
        widget=forms.NumberInput(attrs={"placeholder": _("Min")}),
    )
    price_per_gram_max = django_filters.NumberFilter(
        field_name="price_per_gram",
        lookup_expr="lte",
        label=_("Max Price/g"),
        widget=forms.NumberInput(attrs={"placeholder": _("Max")}),
    )
    concentration_min = django_filters.NumberFilter(
        field_name="concentration",
        lookup_expr="gte",
        label=_("Min Concentration"),
        widget=forms.NumberInput(attrs={"placeholder": _("Min %")}),
    )
    concentration_max = django_filters.NumberFilter(
        field_name="concentration",
        lookup_expr="lte",
        label=_("Max Concentration"),
        widget=forms.NumberInput(attrs={"placeholder": _("Max %")}),
    )

    class Meta:
        model = Product
        fields = [
            "search",
            "price_min",
            "price_max",
            "price_per_gram_min",
            "price_per_gram_max",
            "concentration_min",
            "concentration_max",
        ]

    def filter_queryset(self, queryset: QuerySet[Product]) -> QuerySet[Product]:
        queryset = super().filter_queryset(queryset)

        sort_by = self.data.get("sort_by", "price_per_gram")
        sort_dir = self.data.get("sort_dir", "asc")

        if sort_by not in self.VALID_SORT_FIELDS:
            sort_by = "price_per_gram"
        if sort_dir not in ("asc", "desc"):
            sort_dir = "asc"

        prefix = "-" if sort_dir == "desc" else ""
        return queryset.order_by(f"{prefix}{sort_by}")

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(brand__name__icontains=value)
            | Q(category__name__icontains=value)
            | Q(tags__name__icontains=value)
            | Q(nutrition_profiles__flavors__name__icontains=value)
            | Q(description__icontains=value)
        ).distinct()
