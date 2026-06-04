"""Product nutrition services."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from core.models import Flavor, Micronutrient, NutritionFacts, Product, ProductNutrition

if TYPE_CHECKING:
    from core.dtos import (
        MicronutrientPayload,
        NutritionFactsPayload,
        ProductNutritionPayload,
    )


class ProductNutritionService:
    """Attach typed nutrition profiles to a product."""

    MAX_FACTS_DESCRIPTION_LENGTH = 200
    DEFAULT_MICRONUTRIENT_UNIT = Micronutrient.Units.UNKNOWN

    def attach_profiles(
        self,
        product: Product,
        nutrition_profiles_data: list[ProductNutritionPayload],
    ) -> None:
        """Create nutrition facts and link them to a product."""
        for profile_data in nutrition_profiles_data:
            facts_payload = profile_data.nutrition_facts
            facts = self._create_facts_with_micronutrients(facts_payload)
            profile = self._get_or_create_profile(product, facts)
            self._attach_flavors(profile, profile_data.flavor_names)

    def _create_facts_with_micronutrients(
        self,
        facts_payload: NutritionFactsPayload,
    ) -> NutritionFacts:
        """Create nutrition facts and their micronutrients without deduplication."""
        facts = self._create_facts(facts_payload)
        self._create_micronutrients(facts, facts_payload.micronutrients or [])
        return facts

    def _create_facts(
        self,
        facts_payload: NutritionFactsPayload,
    ) -> NutritionFacts:
        """Persist one nutrition facts table from the submitted payload."""
        return NutritionFacts.objects.create(
            **self._build_facts_defaults(facts_payload),
        )

    def _build_facts_defaults(
        self,
        facts_payload: NutritionFactsPayload,
    ) -> dict[str, str | int | float | Decimal]:
        """Build defaults used when persisting new nutrition facts."""
        return {
            "description": (facts_payload.description or "")[
                : self.MAX_FACTS_DESCRIPTION_LENGTH
            ],
            "serving_size_grams": facts_payload.serving_size_grams,
            "energy_kcal": facts_payload.energy_kcal,
            "proteins": Decimal(str(facts_payload.proteins)),
            "carbohydrates": Decimal(str(facts_payload.carbohydrates)),
            "total_sugars": Decimal(str(facts_payload.total_sugars)),
            "added_sugars": Decimal(str(facts_payload.added_sugars)),
            "total_fats": Decimal(str(facts_payload.total_fats)),
            "saturated_fats": Decimal(str(facts_payload.saturated_fats)),
            "trans_fats": Decimal(str(facts_payload.trans_fats)),
            "dietary_fiber": Decimal(str(facts_payload.dietary_fiber)),
            "sodium": Decimal(str(facts_payload.sodium)),
        }

    def _create_micronutrients(
        self,
        facts: NutritionFacts,
        micronutrient_payloads: list[MicronutrientPayload],
    ) -> None:
        """Persist micronutrients for a freshly created facts table."""
        if not micronutrient_payloads:
            return

        Micronutrient.objects.bulk_create(
            [
                Micronutrient(
                    nutrition_facts=facts,
                    name=micronutrient_payload.name,
                    value=Decimal(str(micronutrient_payload.value)),
                    unit=self._normalize_micronutrient_unit(
                        micronutrient_payload.unit,
                    ),
                )
                for micronutrient_payload in micronutrient_payloads
            ],
        )

    def _normalize_micronutrient_unit(self, value: str) -> str:
        """Return a supported micronutrient unit or the default fallback."""
        normalized = value.strip()
        valid_units = {choice for choice, _label in Micronutrient.Units.choices}
        if normalized in valid_units:
            return normalized
        return self.DEFAULT_MICRONUTRIENT_UNIT

    def _get_or_create_profile(
        self,
        product: Product,
        facts: NutritionFacts,
    ) -> ProductNutrition:
        """Create or reuse the link between a product and nutrition facts."""
        profile, _created = ProductNutrition.objects.get_or_create(
            product=product,
            nutrition_facts=facts,
        )
        return profile

    def _attach_flavors(
        self,
        profile: ProductNutrition,
        flavor_names: list[str] | None,
    ) -> None:
        """Attach flavor names to a nutrition profile."""
        if not flavor_names:
            return

        for flavor_name in flavor_names:
            flavor, _created = Flavor.objects.get_or_create(name=flavor_name)
            profile.flavors.add(flavor)
