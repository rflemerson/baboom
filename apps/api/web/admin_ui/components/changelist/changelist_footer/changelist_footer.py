"""Changelist Footer admin UI component."""

from typing import Any

from django_components import Component, register


@register("changelist_footer")
class ChangelistFooterComponent(Component):
    """Footer wrapper for changelist pagination and save actions."""

    template_name = "changelist/changelist_footer/changelist_footer.html"

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Get component context data."""
        cl = kwargs.get("cl")
        has_formset = bool(kwargs.get("show_save"))
        has_results = bool(getattr(cl, "result_count", 0)) if cl else False

        kwargs["show_save"] = has_formset and has_results
        return kwargs
