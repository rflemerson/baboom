from django_components import component


@component.register("list.filters.drawer")
class FilterDrawer(component.Component):
    """Filter drawer component."""

    template_name = "drawer.html"

    def get_context_data(self, filter_obj):
        """Prepare filter context."""
        return {
            "filter": filter_obj,
        }
