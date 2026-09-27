"""Admin-facing forms for core domain workflows."""

from __future__ import annotations

from django import forms

from .models import Product


class ProductAdminForm(forms.ModelForm):
    """Service-backed admin form for product create and metadata update flows."""

    class Meta:
        """Meta options."""

        model = Product
        fields = (
            "name",
            "kind",
            "brand",
            "net_mass",
            "ean",
            "description",
            "packaging",
            "category",
            "tags",
            "is_published",
        )
