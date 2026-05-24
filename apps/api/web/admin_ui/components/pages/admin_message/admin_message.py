"""Admin Message admin UI component."""

from typing import Any

from django_components import Component, register


@register("admin_message")
class AdminMessageComponent(Component):
    """Simple content message block for auxiliary admin pages."""

    template_name = "pages/admin_message/admin_message.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
