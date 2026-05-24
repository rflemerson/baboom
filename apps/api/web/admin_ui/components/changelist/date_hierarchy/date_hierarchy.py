"""Date Hierarchy admin UI component."""

from typing import Any

from django.contrib.admin.templatetags.admin_list import (
    date_hierarchy as admin_date_hierarchy,
)
from django_components import Component, register


@register("date_hierarchy")
class DateHierarchyComponent(Component):
    """Date hierarchy navigation for changelist pages."""

    template_name = "changelist/date_hierarchy/date_hierarchy.html"

    def get_context_data(
        self,
        cl: object,
        *_args: object,
        **_kwargs: object,
    ) -> dict[str, Any]:
        """Get component context data."""
        return admin_date_hierarchy(cl)  # type: ignore[arg-type]
