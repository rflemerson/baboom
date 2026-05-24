"""Filter admin UI component."""

from typing import Any

from django_components import Component, register


@register("filter")
class FilterComponent(Component):
    """Single changelist filter section."""

    template_name = "changelist/filter/filter.html"

    def get_context_data(
        self,
        cl: object,
        spec: object,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Get component context data."""
        choices_callable = getattr(spec, "choices", None)
        choices = list(choices_callable(cl)) if choices_callable else []
        return {
            **kwargs,
            "title": str(getattr(spec, "title", "")),
            "choices": choices,
        }
