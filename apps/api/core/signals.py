"""Keep derived catalog data in step with deletes the ORM does not route.

A model's delete() runs only when someone deletes that instance. A queryset
delete, an admin bulk action and a cascade never call it, so the derived rows
are refreshed from signals, which every one of those paths does emit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import (
    ComboActive,
    Product,
    ProductActive,
    ProductComponent,
    ProductNutrition,
)

if TYPE_CHECKING:
    from django.db.models import Model


@receiver(post_delete, sender=ProductComponent)
def refresh_combo_after_component_removed(
    sender: type[Model],
    instance: ProductComponent,
    **kwargs: object,
) -> None:
    """Recompute the combo a component line no longer belongs to."""
    _ = sender, kwargs
    combo = Product.objects.filter(pk=instance.parent_id).first()
    if combo is not None:
        ComboActive.objects.sync_for(combo)


@receiver(post_delete, sender=ProductNutrition)
def refresh_actives_after_profile_removed(
    sender: type[Model],
    instance: ProductNutrition,
    **kwargs: object,
) -> None:
    """Recompute a product's concentrations, and the combos holding it."""
    _ = sender, kwargs
    product = Product.objects.filter(pk=instance.product_id).first()
    if product is not None:
        ProductActive.objects.sync_for(product)
