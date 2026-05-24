"""Admin Rich Message admin UI component."""

from typing import Any

from django_components import Component, register


@register("admin_rich_message")
class AdminRichMessageComponent(Component):
    """Heading and HTML-capable message block for auxiliary admin pages."""

    template_name = "pages/admin_rich_message/admin_rich_message.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
