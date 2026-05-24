"""Popup Response admin UI component."""

from typing import Any

from django_components import Component, register


@register("popup_response")
class PopupResponseComponent(Component):
    """Popup response payload page for related-object popups."""

    template_name = "pages/popup_response/popup_response.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
