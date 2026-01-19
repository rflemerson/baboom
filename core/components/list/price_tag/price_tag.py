from django_components import component


@component.register("list.price_tag")
class PriceTag(component.Component):
    template_name = "price_tag.html"

    def get_context_data(
        self,
        price,
        unit_price=None,
        unit_label="R$/g",
        total_protein=None,
        external_link="#",
    ):
        return {
            "price": price,
            "unit_price": unit_price,
            "unit_label": unit_label,
            "total_protein": total_protein,
            "external_link": external_link,
        }
