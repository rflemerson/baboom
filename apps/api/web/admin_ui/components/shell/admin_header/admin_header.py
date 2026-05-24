"""Admin Header admin UI component."""

from typing import Any

from django_components import Component, register


@register("admin_header")
class AdminHeaderComponent(Component):
    """Navbar header component for the administration dashboard."""

    template_name = "shell/admin_header/admin_header.html"

    def get_context_data(
        self,
        *_args: object,
        **_kwargs: object,
    ) -> dict[str, Any]:
        """Prepare context for header rendering."""
        return {}
