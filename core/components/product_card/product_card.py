from django_components import component

@component.register("product_card")
class ProductCard(component.Component):
    template_name = "product_card.html"

    def get_context_data(self, product, variant="grid"):
        return {
            "product": product,
            "variant": variant,
        }
