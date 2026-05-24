"""Filter Sidebar admin UI component."""

from typing import Any

from django_components import Component, register


@register("filter_sidebar")
class FilterSidebarComponent(Component):
    """Sidebar container for changelist filters."""

    template_name = "changelist/filter_sidebar/filter_sidebar.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
