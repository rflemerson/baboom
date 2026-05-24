"""Admin Sidenav admin UI component."""

from typing import Any

from django_components import Component, register


@register("admin_sidenav")
class AdminSidenavComponent(Component):
    """Bootstrap-only collapsible sidebar for Django admin apps."""

    template_name = "shell/admin_sidenav/admin_sidenav.html"

    def get_context_data(
        self,
        available_apps: list[dict[str, Any]],
        current_path: str,
        *_args: object,
        **_kwargs: object,
    ) -> dict[str, Any]:
        """Prepare context for the collapsible sidebar."""
        return {
            "available_apps": available_apps,
            "current_path": current_path,
        }
