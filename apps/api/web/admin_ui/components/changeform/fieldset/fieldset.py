"""Fieldset admin UI component."""

from typing import Any

from django_components import Component, register


@register("fieldset")
class FieldsetComponent(Component):
    """Fieldset renderer for the change form."""

    template_name = "changeform/fieldset/fieldset.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
