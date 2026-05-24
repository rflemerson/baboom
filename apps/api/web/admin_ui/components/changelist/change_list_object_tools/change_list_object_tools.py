"""Change List Object Tools admin UI component."""

from typing import Any

from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.urls import reverse
from django_components import Component, register


@register("change_list_object_tools")
class ChangeListObjectToolsComponent(Component):
    """Object tools for the changelist."""

    template_name = "changelist/change_list_object_tools/change_list_object_tools.html"

    def get_context_data(  # noqa: PLR0913
        self,
        *,
        cl: object,
        preserved_filters: str,
        preserved_qsl: object,
        is_popup: bool,
        to_field: str | None,
        has_add_permission: bool,
        opts: object,
        **_kwargs: object,
    ) -> dict[str, Any]:
        """Get component context data."""
        cl_opts = getattr(cl, "opts", None)
        app_label = getattr(cl_opts, "app_label", "") if cl_opts else ""
        model_name = getattr(cl_opts, "model_name", "") if cl_opts else ""

        add_url = add_preserved_filters(
            {
                "opts": opts,
                "preserved_filters": preserved_filters,
                "preserved_qsl": preserved_qsl,
            },
            reverse(f"admin:{app_label}_{model_name}_add"),
            is_popup,
            to_field,
        )
        return {
            "has_add_permission": has_add_permission,
            "add_url": add_url,
            "opts": opts,
        }
