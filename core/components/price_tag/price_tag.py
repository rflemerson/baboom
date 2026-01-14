from django_components import component

@component.register("price_tag")
class PriceTag(component.Component):
    template_name = "price_tag.html"

    def get_context_data(self, price, unit_price=None, unit_label="R$/g", align="center"):
        return {
            "price": price,
            "unit_price": unit_price,
            "unit_label": unit_label,
            "align": align,
        }
