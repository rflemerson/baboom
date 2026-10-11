"""Publish v2 of the public policies, without the retired price freshness.

A base price now holds until the next read replaces it. Published policies
are frozen, so the rule leaves through a new number; v1 stops being the
default and its disposable projections go.
"""

from django.db import migrations
from django.utils import timezone

KEYS = ("normal", "best")


def publish(apps, schema_editor):
    """Copy each v1 into a published v2 without ``freshness_hours``."""
    _ = schema_editor
    policy = apps.get_model("pricing", "PricingPolicyRevision")
    projection = apps.get_model("pricing", "OfferScenarioProjection")
    for key in KEYS:
        first = policy.objects.filter(key=key, number=1).first()
        if first is None or policy.objects.filter(key=key, number=2).exists():
            continue
        rules = {name: value for name, value in first.rules.items() if name != "freshness_hours"}
        policy.objects.create(
            key=key,
            number=2,
            market_id=first.market_id,
            scenario=first.scenario,
            rules=rules,
            is_default=first.is_default,
            published_at=timezone.now(),
        )
        policy.objects.filter(pk=first.pk).update(is_default=False)
        projection.objects.filter(policy=first).delete()


class Migration(migrations.Migration):
    """Retire price freshness from the public policies."""

    dependencies = (("pricing", "0005_drop_price_freshness"),)

    operations = (migrations.RunPython(publish, migrations.RunPython.noop),)
