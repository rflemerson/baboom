"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

from django.test import TestCase

from core.models import (
    NutritionFacts,
)
from core.tests.helpers import (
    _grams,
)


class NutritionFactsPartialLabelTests(TestCase):
    """Coverage for labels that extraction could only fill in part."""

    def test_partial_label_is_stored_and_hashed(self) -> None:
        """Unknown macros stay null instead of being recorded as zero."""
        facts = NutritionFacts.objects.create(
            description="Parcial",
            proteins=_grams(24),
        )

        facts.refresh_from_db()
        assert facts.serving_size is None
        assert facts.energy is None
        assert facts.content_hash != ""

    def test_null_and_zero_macros_hash_differently(self) -> None:
        """An unknown value is not the same fact as a measured zero."""
        unknown = NutritionFacts.objects.create(proteins=_grams(24))
        measured = NutritionFacts.objects.create(
            proteins=_grams(24),
            carbohydrates=_grams(0),
        )

        assert unknown.content_hash != measured.content_hash
