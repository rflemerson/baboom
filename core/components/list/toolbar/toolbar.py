from django_components import component


@component.register("list.toolbar")
class Toolbar(component.Component):
    """Toolbar component."""

    template_name = "toolbar.html"

    def get_context_data(self, filter_obj, query_params=None):
        """Prepare toolbar context with search/filter."""
        params = query_params or {}
        search_values = params.get("search", [])
        return {
            "filter": filter_obj,
            "search": search_values[0] if search_values else "",
        }
