from django_components import component


@component.register("list.card_list")
class CardList(component.Component):
    template_name = "card_list.html"

    def get_context_data(self, product):
        return {
            "product": product,
        }
