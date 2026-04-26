"""Approval workflow for staged scraper agent extractions."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from pydantic import ValidationError as PydanticValidationError

from core.dtos import (
    ComboComponentInput,
    MicronutrientPayload,
    NutritionFactsPayload,
    ProductCreateInput,
    ProductNutritionPayload,
    StoreListingPayload,
)
from core.models import Product
from core.services import ProductCreateService, ProductNutritionService

from .dtos import AgentExtractionSubmitInput, ExtractedProductInput
from .models import ScrapedItem, ScrapedItemExtraction


@dataclass(frozen=True, slots=True)
class ApprovedExtraction:
    """Result of approving a staged extraction."""

    extraction: ScrapedItemExtraction
    product: Product


class ScrapedItemExtractionApproveService:
    """Approve a staged extraction by creating/linking catalog records."""

    @transaction.atomic
    def execute(self, *, extraction_id: int) -> ApprovedExtraction:
        """Create a catalog product from one staged extraction."""
        extraction = self._get_extraction(extraction_id)
        if extraction.approved_product_id:
            product = extraction.approved_product
            if product is None:
                raise DjangoValidationError(
                    {"approved_product": _("Approved product was not found.")},
                )
            return ApprovedExtraction(
                extraction=extraction,
                product=product,
            )

        data = self._validate_extraction_payload(extraction)
        product = ProductCreateService().execute(
            self._build_product_create_input(extraction=extraction, data=data),
        )

        extraction.approved_product = product
        extraction.approved_at = timezone.now()
        extraction.save(update_fields=["approved_product", "approved_at", "updated_at"])
        return ApprovedExtraction(extraction=extraction, product=product)

    def _get_extraction(self, extraction_id: int) -> ScrapedItemExtraction:
        """Load a staged extraction with the source objects needed for approval."""
        extraction = (
            ScrapedItemExtraction.objects.select_related(
                "approved_product",
                "scraped_item",
                "source_page",
            )
            .filter(id=extraction_id)
            .first()
        )
        if extraction is None:
            raise DjangoValidationError({"extraction": _("Extraction not found.")})
        return extraction

    def _validate_extraction_payload(
        self,
        extraction: ScrapedItemExtraction,
    ) -> AgentExtractionSubmitInput:
        """Revalidate the staged JSON before turning it into catalog data."""
        try:
            return AgentExtractionSubmitInput.model_validate(
                {
                    "originScrapedItemId": extraction.scraped_item_id,
                    "sourcePageId": extraction.source_page_id,
                    "sourcePageUrl": extraction.source_page.url,
                    "storeSlug": extraction.scraped_item.store_slug,
                    "imageReport": extraction.image_report,
                    "product": extraction.extracted_product,
                },
            )
        except PydanticValidationError as exc:
            errors = {str(error["loc"]): [error["msg"]] for error in exc.errors()}
            raise DjangoValidationError(errors) from exc

    def _build_product_create_input(
        self,
        *,
        extraction: ScrapedItemExtraction,
        data: AgentExtractionSubmitInput,
    ) -> ProductCreateInput:
        """Map a validated extraction into the catalog product creation DTO."""
        product = data.product
        self._validate_required_root_fields(product)
        return ProductCreateInput(
            name=str(product.name),
            weight=product.weight_grams,
            brand_name=str(product.brand_name),
            category_name=product.category_hierarchy or None,
            ean=product.ean or None,
            description=product.description or "",
            origin_scraped_item_id=extraction.scraped_item_id,
            packaging=self._resolve_packaging(product.packaging),
            is_published=False,
            tags=product.tags_hierarchy or None,
            stores=[self._build_store_listing(extraction.scraped_item)],
            nutrition=self._build_nutrition_profiles(product),
            is_combo=bool(product.children),
            components=[
                self._build_component_input(child, parent=product)
                for child in product.children
            ]
            or None,
        )

    def _build_component_input(
        self,
        product: ExtractedProductInput,
        *,
        parent: ExtractedProductInput,
    ) -> ComboComponentInput:
        """Map one extracted child product into a combo component DTO."""
        self._validate_required_component_fields(product, parent)
        return ComboComponentInput(
            name=str(product.name),
            weight=product.weight_grams,
            brand_name=product.brand_name or parent.brand_name,
            category_name=product.category_hierarchy or parent.category_hierarchy,
            ean=product.ean or None,
            description=product.description or "",
            packaging=self._resolve_packaging(product.packaging),
            tags=product.tags_hierarchy or None,
            stores=None,
            nutrition=self._build_nutrition_profiles(product),
            quantity=product.quantity or 1,
        )

    def _build_store_listing(self, item: ScrapedItem) -> StoreListingPayload:
        """Build the origin store listing required to link the scraped item."""
        if item.price is None:
            raise DjangoValidationError(
                {"scraped_item": _("Scraped item price is required for approval.")},
            )
        if not item.source_page:
            raise DjangoValidationError(
                {"scraped_item": _("Scraped item source page is required.")},
            )
        return StoreListingPayload(
            store_name=item.store_slug,
            product_link=item.source_page.url,
            price=float(item.price),
            external_id=item.external_id,
            stock_status=item.stock_status or ScrapedItem.StockStatus.AVAILABLE,
        )

    def _build_nutrition_profiles(
        self,
        product: ExtractedProductInput,
    ) -> list[ProductNutritionPayload]:
        """Build nutrition profiles only when required numeric facts exist."""
        facts = product.nutrition_facts
        if facts is None:
            return []

        required_values = (
            facts.serving_size_grams,
            facts.energy_kcal,
            facts.proteins,
            facts.carbohydrates,
            facts.total_fats,
        )
        if any(value is None for value in required_values):
            return []

        return [
            ProductNutritionPayload(
                flavor_names=product.flavor_names,
                nutrition_facts=NutritionFactsPayload(
                    description=facts.description or "",
                    serving_size_grams=float(facts.serving_size_grams),
                    energy_kcal=int(facts.energy_kcal),
                    proteins=float(facts.proteins),
                    carbohydrates=float(facts.carbohydrates),
                    total_fats=float(facts.total_fats),
                    total_sugars=float(facts.total_sugars or 0),
                    added_sugars=float(facts.added_sugars or 0),
                    saturated_fats=float(facts.saturated_fats or 0),
                    trans_fats=float(facts.trans_fats or 0),
                    dietary_fiber=float(facts.dietary_fiber or 0),
                    sodium=float(facts.sodium or 0),
                    micronutrients=[
                        MicronutrientPayload(
                            name=micronutrient.name,
                            value=float(micronutrient.value),
                            unit=micronutrient.unit
                            or ProductNutritionService.DEFAULT_MICRONUTRIENT_UNIT,
                        )
                        for micronutrient in facts.micronutrients
                        if micronutrient.value is not None
                    ],
                ),
            ),
        ]

    def _resolve_packaging(self, value: str | None) -> str:
        """Return a valid catalog packaging value."""
        valid_values = {choice[0] for choice in Product.Packaging.choices}
        if value in valid_values:
            return str(value)
        return Product.Packaging.OTHER

    def _validate_required_root_fields(self, product: ExtractedProductInput) -> None:
        """Reject extracted roots that cannot create a catalog product."""
        errors = {}
        if not product.name:
            errors["product.name"] = _("Product name is required.")
        if not product.brand_name:
            errors["product.brandName"] = _("Product brand is required.")
        if errors:
            raise DjangoValidationError(errors)

    def _validate_required_component_fields(
        self,
        product: ExtractedProductInput,
        parent: ExtractedProductInput,
    ) -> None:
        """Reject component nodes that cannot create/link catalog components."""
        errors = {}
        if not product.name:
            errors["children.name"] = _("Component name is required.")
        if not product.brand_name and not parent.brand_name:
            errors["children.brandName"] = _("Component brand is required.")
        if errors:
            raise DjangoValidationError(errors)
