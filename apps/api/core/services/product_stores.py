"""Product store listing services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import Product, ProductStore, Store
from offers.services import OfferObservationService

if TYPE_CHECKING:
    from core.dtos import StoreListingPayload
    from offers.models import Offer


class StoreResolutionService:
    """Resolve curated stores from manager-facing store names."""

    def resolve(self, store_name: str) -> Store:
        """Resolve a store by display name or slug before creating a new one."""
        store_slug = slugify(store_name)
        store = (
            Store.objects.filter(display_name=store_name).first()
            or Store.objects.filter(name=store_slug).first()
        )
        if store is not None:
            return store

        return Store.objects.create(
            name=store_slug,
            display_name=store_name,
        )


class ProductStoreService:
    """Manage product store listings through the official domain workflow."""

    def __init__(
        self,
        *,
        store_resolution: StoreResolutionService | None = None,
        offer_observations: OfferObservationService | None = None,
    ) -> None:
        """Initialize collaborators for listing synchronization."""
        self.store_resolution = store_resolution or StoreResolutionService()
        self.offer_observations = offer_observations or OfferObservationService()

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
                store = self.store_resolution.resolve(store_payload.store_name)
                if store.id in desired_store_ids:
                    raise ValidationError(
                        {"store": _("A store can only appear once per product.")},
                    )

                desired_store_ids.add(store.id)
                offer = self.offer_observations.resolve_for_listing(
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
