"""Admin-facing forms for core domain workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.core.exceptions import ValidationError

from .models import NutritionFacts, Product, ProductPriceHistory, ProductStore, Store

if TYPE_CHECKING:
    from .models import ProductNutrition


class ProductAdminForm(forms.ModelForm):
    """Service-backed admin form for product create and metadata update flows."""

    REQUIRED_NEW_NUTRITION_FIELDS = (
        "serving_size_grams",
        "energy_kcal",
        "proteins",
        "carbohydrates",
        "total_fats",
    )

    class NutritionMode:
        """Ways the admin can manage nutrition for a product."""

        NONE = "none"
        EXISTING = "existing"
        NEW = "new"
        CHOICES = (
            (NONE, "No nutrition profile"),
            (EXISTING, "Use existing nutrition table"),
            (NEW, "Create or reuse from entered values"),
        )

    nutrition_mode = forms.ChoiceField(
        choices=NutritionMode.CHOICES,
        required=False,
        initial=NutritionMode.NONE,
        label="Nutrition mode",
    )
    existing_nutrition_facts = forms.ModelChoiceField(
        queryset=NutritionFacts.objects.order_by("description", "id"),
        required=False,
        label="Existing nutrition table",
    )
    nutrition_description = forms.CharField(required=False, label="Nutrition label")
    serving_size_grams = forms.DecimalField(required=False, min_value=0)
    energy_kcal = forms.IntegerField(required=False, min_value=0)
    proteins = forms.DecimalField(required=False, min_value=0)
    carbohydrates = forms.DecimalField(required=False, min_value=0)
    total_fats = forms.DecimalField(required=False, min_value=0)
    total_sugars = forms.DecimalField(required=False, min_value=0)
    added_sugars = forms.DecimalField(required=False, min_value=0)
    saturated_fats = forms.DecimalField(required=False, min_value=0)
    trans_fats = forms.DecimalField(required=False, min_value=0)
    dietary_fiber = forms.DecimalField(required=False, min_value=0)
    sodium = forms.DecimalField(required=False, min_value=0)

    class Meta:
        """Meta options."""

        model = Product
        fields = (
            "name",
            "brand",
            "weight",
            "ean",
            "description",
            "packaging",
            "category",
            "tags",
            "is_published",
        )

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Populate nutrition helpers from the current product state."""
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            return

        existing_profile = self._get_existing_nutrition_profile()
        if existing_profile is None:
            self.initial["nutrition_mode"] = self.NutritionMode.NONE
            return

        self.initial.update(
            self._build_existing_nutrition_initial_data(existing_profile),
        )

    def clean(self) -> dict[str, object]:
        """Validate nutrition input according to the selected admin workflow."""
        cleaned_data = super().clean()
        nutrition_mode = cleaned_data.get("nutrition_mode") or self.NutritionMode.NONE

        if nutrition_mode == self.NutritionMode.EXISTING:
            self._validate_existing_nutrition_selection(cleaned_data)
            return cleaned_data

        if nutrition_mode == self.NutritionMode.NEW:
            self._validate_new_nutrition_fields(cleaned_data)

        return cleaned_data

    def _get_existing_nutrition_profile(self) -> ProductNutrition | None:
        """Return the first persisted nutrition profile for the product."""
        return (
            self.instance.nutrition_profiles.select_related("nutrition_facts")
            .order_by("id")
            .first()
        )

    def _build_existing_nutrition_initial_data(
        self,
        existing_profile: ProductNutrition,
    ) -> dict[str, object]:
        """Build initial field values from an existing nutrition profile."""
        facts = existing_profile.nutrition_facts
        return {
            "nutrition_mode": self.NutritionMode.EXISTING,
            "existing_nutrition_facts": facts,
            "nutrition_description": facts.description,
            "serving_size_grams": facts.serving_size_grams,
            "energy_kcal": facts.energy_kcal,
            "proteins": facts.proteins,
            "carbohydrates": facts.carbohydrates,
            "total_fats": facts.total_fats,
            "total_sugars": facts.total_sugars,
            "added_sugars": facts.added_sugars,
            "saturated_fats": facts.saturated_fats,
            "trans_fats": facts.trans_fats,
            "dietary_fiber": facts.dietary_fiber,
            "sodium": facts.sodium,
        }

    def _validate_existing_nutrition_selection(
        self,
        cleaned_data: dict[str, object],
    ) -> None:
        """Require an existing table when that nutrition mode is selected."""
        if cleaned_data.get("existing_nutrition_facts"):
            return

        raise ValidationError(
            {"existing_nutrition_facts": "Select an existing nutrition table."},
        )

    def _validate_new_nutrition_fields(
        self,
        cleaned_data: dict[str, object],
    ) -> None:
        """Require the minimum set of fields for a new nutrition entry."""
        missing_fields = [
            field_name
            for field_name in self.REQUIRED_NEW_NUTRITION_FIELDS
            if cleaned_data.get(field_name) in (None, "")
        ]
        if not missing_fields:
            return

        raise ValidationError(
            dict.fromkeys(
                missing_fields,
                "This field is required when creating nutrition.",
            ),
        )


class ProductStoreInlineForm(forms.ModelForm):
    """Store listing inline that captures a managed listing plus its latest price."""

    price = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    stock_status = forms.ChoiceField(
        required=False,
        choices=ProductPriceHistory.StockStatus.choices,
        initial=ProductPriceHistory.StockStatus.AVAILABLE,
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
        """Populate price helpers from the latest known price snapshot."""
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            return

        latest_price = self._get_latest_price_snapshot()
        if latest_price is None:
            return

        self.initial.update(self._build_latest_price_initial_data(latest_price))

    def _get_latest_price_snapshot(self) -> ProductPriceHistory | None:
        """Return the latest price snapshot for the inline listing."""
        return self.instance.price_history.first()

    def _build_latest_price_initial_data(
        self,
        latest_price: ProductPriceHistory,
    ) -> dict[str, object]:
        """Build initial inline values from the latest price snapshot."""
        return {
            "price": latest_price.price,
            "stock_status": latest_price.stock_status,
        }


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
