"""Publish the first public policies: the store's price, and paid at once."""

from django.db import migrations
from django.utils import timezone

POLICIES = (
    (
        "listed",
        "listed",
        True,
        {
            "accepted_semantics": ["known", "legacy_unknown"],
            "freshness_hours": 72,
        },
    ),
    (
        "cash",
        "cash",
        False,
        {
            "accepted_semantics": ["known"],
            "cash_methods": ["pix", "boleto"],
            "include_unknown_payment": False,
            "freshness_hours": 72,
        },
    ),
)


def publish(apps, schema_editor):
    """Create version 1 of each policy, published."""
    _ = schema_editor
    policy = apps.get_model("pricing", "PricingPolicyRevision")
    for key, scenario, is_default, rules in POLICIES:
        policy.objects.get_or_create(
            key=key,
            number=1,
            defaults={
                "scenario": scenario,
                "is_default": is_default,
                "rules": rules,
                "published_at": timezone.now(),
            },
        )


class Migration(migrations.Migration):
    """Seed the public policies."""

    dependencies = (("pricing", "0001_initial"),)

    operations = (migrations.RunPython(publish, migrations.RunPython.noop),)
