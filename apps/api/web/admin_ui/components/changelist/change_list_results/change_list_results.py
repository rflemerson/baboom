"""Change List Results admin UI component."""

from typing import Any

from django.contrib.admin.templatetags.admin_list import result_list
from django_components import Component, register


@register("change_list_results")
class ChangeListResultsComponent(Component):
    """Results table for the changelist."""

    template_name = "changelist/change_list_results/change_list_results.html"

    def get_context_data(self, cl: object, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return {
            **kwargs,
            **result_list(cl),  # type: ignore[arg-type]
        }
