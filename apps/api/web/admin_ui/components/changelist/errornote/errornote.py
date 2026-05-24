"""Errornote admin UI component."""

from typing import Any

from django_components import Component, register


@register("errornote")
class ErrorNoteComponent(Component):
    """Error summary for changelist formset errors."""

    template_name = "changelist/errornote/errornote.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return kwargs
