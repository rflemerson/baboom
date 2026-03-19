"""Filter definitions for catalog-facing product queries."""

from __future__ import annotations

from typing import ClassVar

import django_filters
from django import forms
from django.db.models import F, Q, QuerySet
from django.utils.translation import gettext_lazy as _

from .models import Product


class ProductFilter(django_filters.FilterSet):
    """Filter set for Products."""

    SORT_CHOICES = (
        ("price_per_gram", _("Price/g")),
        ("last_price", _("Price")),
        ("total_protein", _("Protein")),
        ("concentration", _("Concentration")),
    )
    VALID_SORT_FIELDS: ClassVar[set[str]] = {key for key, _ in SORT_CHOICES}

    search = django_filters.CharFilter(
        method="filter_search",
        label=_("Search"),
        widget=forms.TextInput(attrs={"placeholder": _("Search...")}),
    )

    brand = django_filters.CharFilter(
        field_name="brand__name",
        lookup_expr="icontains",
        label=_("Brand"),
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
        """Meta options."""

        model = Product
        fields = (
            "search",
            "brand",
            "price_min",
            "price_max",
            "price_per_gram_min",
            "price_per_gram_max",
            "concentration_min",
            "concentration_max",
        )

    def filter_queryset(self, queryset: QuerySet[Product]) -> QuerySet[Product]:
        """Apply filters and sorting."""
        queryset = super().filter_queryset(queryset)

        sort_by = self.data.get("sort_by", "price_per_gram")
        sort_dir = self.data.get("sort_dir", "asc")

        if sort_by not in self.VALID_SORT_FIELDS:
            sort_by = "price_per_gram"
        if sort_dir not in ("asc", "desc"):
            sort_dir = "asc"

        prefix = "-" if sort_dir == "desc" else ""

        if sort_by in [
            "price_per_gram",
            "last_price",
            "concentration",
            "total_protein",
        ]:
            if prefix == "-":
                return queryset.order_by(F(sort_by).desc(nulls_last=True))
            return queryset.order_by(F(sort_by).asc(nulls_last=True))

        return queryset.order_by(f"{prefix}{sort_by}")

    def filter_search(
        self,
        queryset: QuerySet[Product],
        _name: str,
        value: str | None,
    ) -> QuerySet[Product]:
        """Filter by search query."""
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(brand__name__icontains=value)
            | Q(category__name__icontains=value)
            | Q(tags__name__icontains=value)
            | Q(nutrition_profiles__flavors__name__icontains=value)
            | Q(description__icontains=value),
        ).distinct()
