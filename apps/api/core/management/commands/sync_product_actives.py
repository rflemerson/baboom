"""Rebuild the derived product concentrations from nutrition data."""

from django.core.management.base import BaseCommand

from core.models import Product, ProductActive


class Command(BaseCommand):
    """Recompute :class:`ProductActive` rows for every product."""

    help = "Rebuild product active concentrations from nutrition profiles."

    def handle(self, *_args: object, **_options: object) -> None:
        """Sync every product and report how many rows resulted."""
        products = Product.objects.prefetch_related(
            "nutrition_profiles__nutrition_facts__actives",
        )
        for product in products.iterator(chunk_size=100):
            ProductActive.objects.sync_for(product)

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {ProductActive.objects.count()} product active rows.",
            ),
        )
