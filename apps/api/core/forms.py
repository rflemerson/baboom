"""Admin-facing forms for core domain workflows."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from offers.models import StockStatus

from .models import Product, ProductStore, Store
from .units import DISPLAY_MASS_UNIT, from_canonical


class ProductAdminForm(forms.ModelForm):
    """Service-backed admin form for product create and metadata update flows.

    Masses are stored canonically but edited in the unit the catalog presents,
    so the operator never types a converted number.
    """

    net_mass = forms.DecimalField(
        required=False,
        min_value=0,
        label=f"Net mass ({DISPLAY_MASS_UNIT})",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Show the stored canonical mass in the display unit."""
        super().__init__(*args, **kwargs)
        stored = getattr(self.instance, "net_mass", None)
        if stored is not None:
            self.initial["net_mass"] = from_canonical(stored, DISPLAY_MASS_UNIT)

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


class ProductStoreInlineForm(forms.ModelForm):
    """Store listing inline that captures a managed listing plus its latest price.

    ``external_id`` and ``product_link`` are merchant-offer fields surfaced here
    so the admin can enter them; the service layer persists them on the offer.
    """

    external_id = forms.CharField(required=False, label="Store Product ID")
    product_link = forms.URLField(required=False, label="Store Product URL")
    price = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    stock_status = forms.ChoiceField(
        required=False,
        choices=StockStatus.choices,
        initial=StockStatus.AVAILABLE,
    )

    class Meta:
        """Meta options."""

        model = ProductStore
        fields = (
            "store",
            "external_id",
            "product_link",
            "affiliate_link",
            "price",
            "stock_status",
        )

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Populate listing and price helpers from the linked merchant offer."""
        super().__init__(*args, **kwargs)

        if not self.instance.pk or self.instance.offer is None:
            return

        self.initial.update(self._build_offer_initial_data())

    def _build_offer_initial_data(self) -> dict[str, object]:
        """Build initial inline values from the linked offer and its latest price."""
        offer = self.instance.offer
        initial: dict[str, object] = {
            "external_id": offer.external_id,
            "product_link": offer.url,
        }
        latest_price = offer.price_observations.first()
        if latest_price is not None:
            initial["price"] = latest_price.price
            initial["stock_status"] = latest_price.stock_status
        return initial


class ProductStoreInlineFormSet(forms.BaseInlineFormSet):
    """Validate store listing rows before sending them through the service layer."""

    LISTING_INPUT_FIELDS = (
        "store",
        "external_id",
        "product_link",
        "affiliate_link",
        "price",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Provide the change-tracking attributes Django admin expects."""
        super().__init__(*args, **kwargs)
        self.new_objects: list[ProductStore] = []
        self.changed_objects: list[tuple[ProductStore, list[str]]] = []
        self.deleted_objects: list[ProductStore] = []

    def clean(self) -> None:
        """Require a current price for every non-deleted store listing row."""
        super().clean()
        seen_store_ids: set[int] = set()

        for form in self.forms:
            cleaned_data = getattr(form, "cleaned_data", None)
            if self._can_skip_cleaned_row(cleaned_data):
                continue

            if not self._has_store_listing_data(cleaned_data):
                continue

            self._validate_unique_store(cleaned_data, seen_store_ids)

            if not cleaned_data.get("external_id"):
                error_message = "Each store listing requires a store product ID."
                raise ValidationError(error_message)

            if cleaned_data.get("price") in (None, ""):
                error_message = "Each store listing requires a current price."
                raise ValidationError(error_message)

    def _can_skip_cleaned_row(self, cleaned_data: dict[str, object] | None) -> bool:
        """Return whether a row can be ignored during inline validation."""
        return not cleaned_data or bool(cleaned_data.get("DELETE"))

    def _has_store_listing_data(self, cleaned_data: dict[str, object]) -> bool:
        """Return whether the row contains any meaningful listing input."""
        return any(
            cleaned_data.get(field_name) for field_name in self.LISTING_INPUT_FIELDS
        )

    def _validate_unique_store(
        self,
        cleaned_data: dict[str, object],
        seen_store_ids: set[int],
    ) -> None:
        """Reject duplicate stores before the payload reaches the service layer."""
        store = cleaned_data.get("store")
        if not isinstance(store, Store):
            return

        if store.id in seen_store_ids:
            error_message = "A store can only appear once per product."
            raise ValidationError(error_message)

        seen_store_ids.add(store.id)
