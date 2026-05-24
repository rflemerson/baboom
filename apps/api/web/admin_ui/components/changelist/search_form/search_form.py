"""Search Form admin UI component."""

from typing import Any

from django.contrib.admin.views.main import IS_FACETS_VAR, IS_POPUP_VAR, SEARCH_VAR
from django_components import Component, register


@register("search_form")
class SearchFormComponent(Component):
    """Search form for the changelist."""

    template_name = "changelist/search_form/search_form.html"

    def get_context_data(self, cl: object, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        result_count = getattr(cl, "result_count", 0)
        full_result_count = getattr(cl, "full_result_count", 0)
        return {
            **kwargs,
            "cl": cl,
            "search_var": SEARCH_VAR,
            "is_popup_var": IS_POPUP_VAR,
            "is_facets_var": IS_FACETS_VAR,
            "show_result_count": result_count != full_result_count,
        }
