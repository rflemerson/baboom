from typing import cast

import strawberry
from django.core.exceptions import ValidationError as DjangoValidationError

from baboom.utils import format_graphql_errors
from core.models import Product
from core.services import product_create, product_update_content

from .inputs import ProductContentUpdateInput, ProductInput
from .types import ProductResult, ProductType


@strawberry.type
class CoreMutation:
    @strawberry.mutation
    def create_product(self, data: ProductInput) -> ProductResult:
        stores_data = []
        if data.stores:
            for s in data.stores:
                stores_data.append(
                    {
                        "store_name": s.store_name,
                        "product_link": s.product_link,
                        "price": s.price,
                        "external_id": s.external_id,
                        "affiliate_link": s.affiliate_link,
                        "stock_status": s.stock_status.value,
                    }
                )

        nutrition_data = []
        if data.nutrition:
            for n in data.nutrition:
                facts = n.nutrition_facts
                micronutrients_data = []
                if facts.micronutrients:
                    for m in facts.micronutrients:
                        micronutrients_data.append(
                            {"name": m.name, "value": m.value, "unit": m.unit}
                        )

                nutrition_data.append(
                    {
                        "flavor_names": n.flavor_names,
                        "nutrition_facts": {
                            "description": facts.description,
                            "serving_size_grams": facts.serving_size_grams,
                            "energy_kcal": facts.energy_kcal,
                            "proteins": facts.proteins,
                            "carbohydrates": facts.carbohydrates,
                            "total_sugars": facts.total_sugars,
                            "added_sugars": facts.added_sugars,
                            "total_fats": facts.total_fats,
                            "saturated_fats": facts.saturated_fats,
                            "trans_fats": facts.trans_fats,
                            "dietary_fiber": facts.dietary_fiber,
                            "sodium": facts.sodium,
                            "micronutrients": micronutrients_data,
                        },
                    }
                )

        try:
            product = product_create(
                name=data.name,
                weight=data.weight,
                brand_name=data.brand_name,
                category_name=data.category_name,
                ean=data.ean,
                description=data.description,
                packaging=data.packaging.value,
                is_published=data.is_published,
                tags=data.tags,
                stores=stores_data,
                nutrition=nutrition_data,
            )
            return ProductResult(product=cast(ProductType, product))

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))

    @strawberry.mutation
    def update_product_content(
        self, product_id: int, data: ProductContentUpdateInput
    ) -> ProductResult:
        product = Product.objects.filter(id=product_id).first()
        if not product:
            from baboom.utils import ValidationError as GqlValidationError

            return ProductResult(
                errors=[
                    GqlValidationError(field="product_id", message="Product not found")
                ]
            )

        try:
            updated_product = product_update_content(
                product=product,
                name=data.name,
                description=data.description,
                category_name=data.category_name,
                packaging=data.packaging.value if data.packaging else None,
                tags=data.tags,
            )
            return ProductResult(product=cast(ProductType, updated_product))

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))
