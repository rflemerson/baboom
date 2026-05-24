"""Submit Line admin UI component."""

from typing import Any

from django.contrib.admin.templatetags.admin_modify import submit_row
from django_components import Component, register


@register("submit_line")
class SubmitLineComponent(Component):
    """Submit row for the change form."""

    template_name = "changeform/submit_line/submit_line.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return submit_row(kwargs).flatten()
