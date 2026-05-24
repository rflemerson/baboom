"""Minimal base admin helpers for component-backed Django admin chrome."""

from __future__ import annotations

import contextlib
from typing import Any

from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.text import Truncator, capfirst
from django.utils.translation import gettext as _


class BaseAdmin(admin.ModelAdmin):
    """Inject shared navigation context into standard Django admin pages."""

    change_list_template = "admin/change_list.html"

    def _build_breadcrumb_items(
        self,
        request: object,
        _object_id: str | None = None,
        extra_label: str | None = None,
    ) -> list[dict[str, str | None]]:
        """Build standard admin breadcrumbs for the current model."""
        home_url = None
        with contextlib.suppress(NoReverseMatch):
            home_url = reverse("admin:index")

        app_url = None
        with contextlib.suppress(NoReverseMatch):
            app_url = reverse(
                "admin:app_list",
                kwargs={"app_label": self.opts.app_label},
            )

        changelist_url = None
        if self.has_view_permission(request):  # type: ignore[arg-type]
            with contextlib.suppress(NoReverseMatch):
                changelist_url = reverse(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist",
                )

        items: list[dict[str, str | None]] = [
            {"label": "Home", "url": home_url},
            {
                "label": self.opts.app_config.verbose_name,
                "url": app_url,
            },
            {"label": capfirst(self.opts.verbose_name_plural), "url": changelist_url},
        ]

        if extra_label:
            items.append({"label": extra_label, "url": None})

        return items

    def _with_admin_shell_context(
        self,
        request: object,
        extra_context: dict[str, Any] | None = None,
        *,
        object_id: str | None = None,
        extra_label: str | None = None,
    ) -> dict[str, Any]:
        """Merge shell/navigation context into any admin page extra_context."""
        context = dict(extra_context or {})
        context.setdefault("available_apps", self.admin_site.get_app_list(request))  # type: ignore[arg-type]
        context.setdefault(
            "component_breadcrumb_items",
            self._build_breadcrumb_items(request, object_id, extra_label),
        )
        return context

    def changelist_view(
        self,
        request: object,
        extra_context: dict[str, Any] | None = None,
    ) -> object:
        """Render the standard changelist with component-backed admin chrome."""
        return super().changelist_view(
            request,
            self._with_admin_shell_context(request, extra_context),
        )

    def render_change_form(  # noqa: PLR0913
        self,
        request: object,
        context: dict[str, Any],
        add: bool = False,  # noqa: FBT001, FBT002
        change: bool = False,  # noqa: FBT001, FBT002
        form_url: str = "",
        obj: object | None = None,
    ) -> object:
        """Inject shell/navigation context into the standard Django change form."""
        extra_label = (
            _("Add %(name)s") % {"name": self.opts.verbose_name}
            if add
            else Truncator(str(obj)).words(18)
        )
        pk = getattr(obj, "pk", None)
        shell_context = self._with_admin_shell_context(
            request,
            context,
            object_id=str(pk) if pk is not None else None,
            extra_label=extra_label,
        )
        return super().render_change_form(
            request,
            shell_context,
            add=add,
            change=change,
            form_url=form_url,
            obj=obj,  # type: ignore[arg-type]
        )
