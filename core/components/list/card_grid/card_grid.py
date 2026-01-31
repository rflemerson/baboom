from django_components import component


@component.register("list.card_grid")
class CardGrid(component.Component):
    """Card grid component."""

    template_name = "card_grid.html"

    def get_context_data(self, product):
        """Prepare product context."""
        return {
            "product": product,
        }
