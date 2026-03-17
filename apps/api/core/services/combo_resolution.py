"""Services for resolving combo products into concrete components."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from core.models import Product, ProductComponent

if TYPE_CHECKING:
    from core.types import ProductComponentInput


MATCH_SCORE_THRESHOLD = 0.6


class ComboResolutionService:
    """Service to resolve and link components for Combo products."""

    def resolve_combo_components(
        self,
        parent_product: Product,
        components_data: list[ProductComponentInput],
    ) -> list[ProductComponent]:
        """Resolve component DTOs to existing products or placeholders."""
        created_links = []

        # Clear existing links to avoid duplication if re-running
        parent_product.component_links.all().delete()

        for comp_data in components_data:
            match = self._find_best_match(
                name=comp_data.name,
                brand_id=parent_product.brand_id,
                weight_hint=comp_data.weight_hint,
                packaging_hint=comp_data.packaging_hint,
            )

            if match:
                component_product = match
            else:
                component_product = self._create_placeholder(comp_data, parent_product)

            link = ProductComponent.objects.create(
                parent=parent_product,
                component=component_product,
                quantity=comp_data.quantity,
            )
            created_links.append(link)

        return created_links

    def _find_best_match(
        self,
        name: str,
        brand_id: int,
        weight_hint: int | None,
        packaging_hint: str | None,
    ) -> Product | None:
        """Smart matching strategy.

        1. Filter by Brand.
        2. Filter by Weight (if available).
        3. Fuzzy match Name.
        """
        qs = Product.objects.filter(brand_id=brand_id, type=Product.Type.SIMPLE)

        # 1. Weight Filter (Relaxed window +/- 10%)
        if weight_hint:
            min_w = weight_hint * 0.9
            max_w = weight_hint * 1.1
            qs = qs.filter(weight__gte=min_w, weight__lte=max_w)

        # 2. Packaging Filter (Optional)
        # Basic mapping if user string matches enum
        if packaging_hint and packaging_hint.upper() in Product.Packaging.values:
            qs = qs.filter(packaging=packaging_hint.upper())

        candidates = list(qs)
        if not candidates:
            return None

        # 3. Fuzzy Match
        best_candidate = None
        best_score = 0.0

        # Heuristic: Remove brand name/common words effectively?
        # For now, simplistic comparison
        target_name = name.lower()

        for cand in candidates:
            score = SequenceMatcher(None, target_name, cand.name.lower()).ratio()
            if score > best_score:
                best_score = score
                best_candidate = cand

        # Threshold for acceptance
        if best_score > MATCH_SCORE_THRESHOLD:
            return best_candidate

        return None

    def _create_placeholder(
        self,
        comp_data: ProductComponentInput,
        parent: Product,
    ) -> Product:
        """Create a placeholder product when no match is found."""
        return Product.objects.create(
            name=f"[Placeholder] {comp_data.name}",
            brand=parent.brand,  # Assume same brand or we can't save
            weight=comp_data.weight_hint or 0,
            description=f"Auto-generated placeholder for component of {parent.name}",
            is_published=False,
        )
