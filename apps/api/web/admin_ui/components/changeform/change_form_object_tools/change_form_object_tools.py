"""Change Form Object Tools admin UI component."""

from typing import Any

from django_components import Component, register


@register("change_form_object_tools")
class ChangeFormObjectToolsComponent(Component):
    """Object tools for the change form."""

    template_name = "changeform/change_form_object_tools/change_form_object_tools.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
