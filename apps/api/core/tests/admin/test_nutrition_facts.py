"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

from unittest.mock import Mock

from django.contrib import admin as django_admin
from django.test import RequestFactory, TestCase

from core.admin import NutritionFactsAdmin
from core.models import (
    NutritionFacts,
)


class NutritionFactsAdminTests(TestCase):
    """Coverage for manager-facing nutrition admin behavior."""

    def test_nutrition_facts_can_be_deleted_from_admin(self) -> None:
        """Nutrition tables are normal manager-owned catalog records."""
        nutrition_admin = NutritionFactsAdmin(NutritionFacts, django_admin.site)
        request = RequestFactory().get("/admin/core/nutritionfacts/")
        request.user = Mock(has_perm=Mock(return_value=True))

        assert nutrition_admin.has_delete_permission(request) is True
