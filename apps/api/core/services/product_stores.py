"""Product store listing services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from core.models import Product, ProductStore, Store
from offers.services import OfferObservationService

if TYPE_CHECKING:
    from core.dtos import StoreListingPayload
    from offers.models import Offer


class ProductStoreService:
    """Manage product store listings through the official domain workflow."""

    def replace_listings(
        self,
        product: Product,
        store_listings_data: list[StoreListingPayload],
    ) -> None:
        """Synchronize current product store listings with the desired admin state."""
        with transaction.atomic():
            existing_links = {
                product_store.store_id: product_store
                for product_store in product.store_links.select_related(
                    "store",
                    "offer",
                )
            }
            desired_store_ids: set[int] = set()

            for store_payload in store_listings_data:
                store = Store.objects.filter(id=store_payload.store_id).first()
                if store is None:
                    raise ValidationError(
                        {"store_id": _("Store not found.")},
                    )
                if store.id in desired_store_ids:
                    raise ValidationError(
                        {"store": _("A store can only appear once per product.")},
                    )

                desired_store_ids.add(store.id)
                offer = OfferObservationService().resolve_for_listing(
                    store_slug=store.name,
                    listing=store_payload,
                )
                existing_listing = existing_links.get(store.id)
                if existing_listing is None:
                    self._create_listing(product, store, offer, store_payload)
                    continue

                self._update_listing(existing_listing, offer, store_payload)

            self._remove_deleted_listings(existing_links, desired_store_ids)

    def _create_listing(
        self,
        product: Product,
        store: Store,
        offer: Offer,
        store_payload: StoreListingPayload,
    ) -> ProductStore:
        """Create a single store listing bound to its merchant offer."""
        product_store = ProductStore(
            product=product,
            store=store,
            offer=offer,
            affiliate_link=store_payload.affiliate_link or "",
        )
        product_store.full_clean()
        product_store.save()
        return product_store

    def _update_listing(
        self,
        product_store: ProductStore,
        offer: Offer,
        store_payload: StoreListingPayload,
    ) -> None:
        """Update a persisted listing's offer link and affiliate URL."""
        updated_fields: list[str] = []
        resolved_affiliate_link = store_payload.affiliate_link or ""

        if product_store.offer_id != offer.id:
            product_store.offer = offer
            updated_fields.append("offer")
        if product_store.affiliate_link != resolved_affiliate_link:
            product_store.affiliate_link = resolved_affiliate_link
            updated_fields.append("affiliate_link")

        if updated_fields:
            product_store.full_clean()
            product_store.save(update_fields=updated_fields)

    def _remove_deleted_listings(
        self,
        existing_links: dict[int, ProductStore],
        desired_store_ids: set[int],
    ) -> None:
        """Delete store listings that were removed from the desired admin state."""
        for store_id, product_store in existing_links.items():
            if store_id not in desired_store_ids:
                product_store.delete()
