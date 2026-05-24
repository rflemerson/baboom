"""Recent Actions admin UI component."""

from typing import Any

from django_components import Component, register


@register("recent_actions")
class RecentActionsComponent(Component):
    """Recent actions sidebar for the admin index."""

    template_name = "dashboard/recent_actions/recent_actions.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
