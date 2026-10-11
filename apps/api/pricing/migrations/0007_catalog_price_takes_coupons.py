"""Publish ``normal`` v3: the catalog price also takes coupons and cashback.

The catalog price stays the store's own price paid any way (``listed``), with
no cash-method discount; the buyer's coupon and cashback switches now act on
it as on the best price. ``best`` becomes the default the catalog shows.
Published policies are frozen, so the change leaves through a new number and
v2's disposable projections go.
"""

from django.db import migrations
from django.utils import timezone

BENEFITS = {
    "allow_codes": True,
    "auto_public_codes": True,
    "allow_rewards": True,
    "allow_conditions": ["min_amount", "min_quantity", "channel", "market", "seller", "calendar"],
}


def publish(apps, schema_editor):
    """Copy ``normal`` v2 into a v3 that applies benefits; default to ``best``."""
    _ = schema_editor
    policy = apps.get_model("pricing", "PricingPolicyRevision")
    projection = apps.get_model("pricing", "OfferScenarioProjection")
    previous = policy.objects.filter(key="normal", number=2).first()
    best = policy.objects.filter(key="best").order_by("-number").first()
    if previous is None or best is None or policy.objects.filter(key="normal", number=3).exists():
        return
    rules = {name: value for name, value in previous.rules.items() if name != "apply_benefits"}
    policy.objects.filter(is_default=True).update(is_default=False)
    policy.objects.create(
        key="normal",
        number=3,
        market_id=previous.market_id,
        scenario=previous.scenario,
        rules={**rules, **BENEFITS},
        is_default=False,
        published_at=timezone.now(),
    )
    policy.objects.filter(pk=best.pk).update(is_default=True)
    projection.objects.filter(policy=previous).delete()


class Migration(migrations.Migration):
    """Let the catalog price take coupons and cashback."""

    dependencies = (("pricing", "0006_policies_without_freshness"),)

    operations = (migrations.RunPython(publish, migrations.RunPython.noop),)
