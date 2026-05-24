"""Pagination admin UI component."""

from typing import Any

from django.contrib.admin.templatetags.admin_list import pagination
from django_components import Component, register


@register("pagination")
class PaginationComponent(Component):
    """Pagination controls for the changelist."""

    template_name = "changelist/pagination/pagination.html"

    def get_context_data(self, cl: object, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        return {
            **kwargs,
            **pagination(cl),  # type: ignore[arg-type]
        }
