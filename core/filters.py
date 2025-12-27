import django_filters
from django import forms
from django.db.models import Q

from .models import Product


class ProductFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method="filter_search",
        label="Search",
        widget=forms.TextInput(attrs={"placeholder": "Search..."}),
    )
    ordering = django_filters.OrderingFilter(
        fields=(
            ("price_per_gram", "price_per_gram"),
            ("last_price", "price"),
            ("total_protein", "protein"),
            ("concentration", "concentration"),
        ),
        field_labels={
            "price_per_gram": "Price per Gram",
            "last_price": "Total Price",
            "total_protein": "Total Protein",
            "concentration": "Concentration",
        },
        label="Sort by",
    )
    brand = django_filters.AllValuesFilter(
        field_name="brand__name",
        empty_label="Brand",
        widget=forms.Select(),
    )

    class Meta:
        model = Product
        fields = ["search", "brand"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(brand__name__icontains=value)
            | Q(description__icontains=value)
        )
