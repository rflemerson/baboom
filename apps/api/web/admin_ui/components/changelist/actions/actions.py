"""Actions admin UI component."""

from typing import Any

from django_components import Component, register


@register("actions")
class ActionsComponent(Component):
    """Bulk actions area for changelist."""

    template_name = "changelist/actions/actions.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
