"""Breadcrumbs admin UI component."""

from typing import Any

from django_components import Component, register


@register("breadcrumbs")
class BreadcrumbsComponent(Component):
    """Breadcrumb navigation for admin pages."""

    template_name = "shell/breadcrumbs/breadcrumbs.html"

    def get_context_data(
        self,
        items: list[dict[str, Any]],
        *_args: object,
        **_kwargs: object,
    ) -> dict[str, Any]:
        """Prepare breadcrumb items."""
        return {
            "items": items,
        }
