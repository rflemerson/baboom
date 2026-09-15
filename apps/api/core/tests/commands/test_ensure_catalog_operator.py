"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase


class CatalogOperatorCommandTests(TestCase):
    """Coverage for the restricted catalog operator command."""

    EXPECTED_PERMISSION_COUNT = 28

    def test_command_is_idempotent_and_syncs_permissions(self) -> None:
        """Create one staff user and the exact configured permission set."""
        call_command("ensure_catalog_operator", username="catalog-operator")
        call_command("ensure_catalog_operator", username="catalog-operator")

        user = get_user_model().objects.get(username="catalog-operator")
        group = Group.objects.get(name="catalog-operator")
        codenames = set(group.permissions.values_list("codename", flat=True))

        assert user.is_staff is True
        assert user.is_superuser is False
        assert list(user.groups.values_list("pk", flat=True)) == [group.pk]
        assert "add_product" in codenames
        assert "change_nutritionfacts" in codenames
        assert "view_scrapedpage" in codenames
        assert len(codenames) == self.EXPECTED_PERMISSION_COUNT
        assert not any(codename.startswith("delete_") for codename in codenames)

    def test_password_comes_from_the_environment(self) -> None:
        """A credential passed as an argument would land in shell history."""
        with mock.patch.dict(
            os.environ,
            {"CATALOG_OPERATOR_PASSWORD": "chosen-by-the-operator"},
        ):
            call_command(
                "ensure_catalog_operator",
                username="catalog-operator",
                email="curator@local.test",
            )

        user = get_user_model().objects.get(username="catalog-operator")
        assert user.check_password("chosen-by-the-operator")
        assert user.email == "curator@local.test"
        assert user.is_staff
        assert not user.is_superuser
