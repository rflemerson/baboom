"""Empty Results admin UI component."""

from typing import Any

from django_components import Component, register


@register("empty_results")
class EmptyResultsComponent(Component):
    """Empty state for changelist results."""

    template_name = "changelist/empty_results/empty_results.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
