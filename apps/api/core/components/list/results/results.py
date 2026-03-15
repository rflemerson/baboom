from django_components import component


@component.register("list.results")
class ListResults(component.Component):
    """Results list component."""

    template_name = "results.html"

    def get_context_data(self, page_obj, per_page, query_params, view_mode="list"):
        """Prepare results context."""
        return {
            "page_obj": page_obj,
            "per_page": per_page,
            "query_params": query_params,
            "view_mode": view_mode,
        }
