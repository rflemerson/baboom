"""App List admin UI component."""

from typing import Any

from django_components import Component, register


@register("app_list")
class AppListComponent(Component):
    """App/model list used by the admin dashboard pages."""

    template_name = "dashboard/app_list/app_list.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
