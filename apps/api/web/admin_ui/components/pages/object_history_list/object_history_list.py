"""Object History List admin UI component."""

from typing import Any

from django_components import Component, register


@register("object_history_list")
class ObjectHistoryListComponent(Component):
    """History table and paginator for admin object history."""

    template_name = "pages/object_history_list/object_history_list.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
