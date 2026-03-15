from django_components import component


@component.register("list.pagination")
class Pagination(component.Component):
    """Pagination component."""

    template_name = "pagination.html"

    def get_context_data(self, page_obj, per_page=None, query_params=None):
        """Build context with query string."""
        # Build query string from params, excluding 'page'
        params = query_params or {}
        query_parts = [f"{k}={v[0]}" for k, v in params.items() if k != "page" and v]
        query_string = "&".join(query_parts)
        return {
            "page_obj": page_obj,
            "per_page": per_page,
            "query_string": query_string,
        }
