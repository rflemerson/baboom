"""Prepopulated Fields Js admin UI component."""

from typing import Any

from django_components import Component, register


@register("prepopulated_fields_js")
class PrepopulatedFieldsJsComponent(Component):
    """Prepopulated fields bootstrapping script."""

    template_name = "changeform/prepopulated_fields_js/prepopulated_fields_js.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
