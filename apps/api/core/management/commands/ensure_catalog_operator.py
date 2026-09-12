"""Create the restricted catalog operator used by external clients."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

if TYPE_CHECKING:
    from argparse import ArgumentParser


GROUP_NAME = "catalog-operator"

PERMISSIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "core": {
        "product": ("add", "change", "view"),
        "productnutrition": ("add", "change", "view"),
        "nutritionfacts": ("add", "change", "view"),
        "nutritionactive": ("add", "change", "view"),
        "productstore": ("add", "change", "view"),
        "flavor": ("add", "change", "view"),
        "tag": ("add", "change", "view"),
        "brand": ("view",),
        "category": ("view",),
        "active": ("view",),
        "store": ("view",),
    },
    "offers": {"offer": ("view",)},
    "scrapers": {
        "scrapeditem": ("view",),
        "scrapedpage": ("view",),
    },
}


class Command(BaseCommand):
    """Ensure a staff user has the catalog operator permissions."""

    help = "Create or update a restricted catalog operator user."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Register the required username argument."""
        parser.add_argument("--username", required=True)

    def handle(self, *_args: object, **options: object) -> None:
        """Create the group and synchronize its explicit permission set."""
        username = str(options["username"]).strip()
        if not username:
            message = "Username cannot be empty."
            raise CommandError(message)

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        user.is_staff = True
        user.is_active = True
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_active", "is_superuser"])

        group, _group_created = Group.objects.get_or_create(name=GROUP_NAME)
        permissions = []
        for app_label, models in PERMISSIONS.items():
            for model_name, actions in models.items():
                for action in actions:
                    codename = f"{action}_{model_name}"
                    permission = Permission.objects.filter(
                        content_type__app_label=app_label,
                        content_type__model=model_name,
                        codename=codename,
                    ).first()
                    if permission is None:
                        message = (
                            f"Permission {action}_{app_label}.{model_name} "
                            "does not exist."
                        )
                        raise CommandError(message)
                    permissions.append(permission)
        group.permissions.set(permissions)
        user.groups.add(group)

        state = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Operator {username!r} {state}; synchronized "
                f"{len(permissions)} permissions.",
            ),
        )
