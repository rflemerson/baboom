from django_components import component


@component.register("list.filters")
class Filters(component.Component):
    """Filters container component."""

    template_name = "filters.html"

    def get_context_data(self, filter_obj):
        """Prepare filter context."""
        return {
            "filter": filter_obj,
        }
