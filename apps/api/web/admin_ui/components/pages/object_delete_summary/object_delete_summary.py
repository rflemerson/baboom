"""Object Delete Summary admin UI component."""

from typing import Any

from django_components import Component, register


@register("object_delete_summary")
class ObjectDeleteSummaryComponent(Component):
    """Summary block used by delete confirmation pages."""

    template_name = "pages/object_delete_summary/object_delete_summary.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
