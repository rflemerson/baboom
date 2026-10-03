"""Admin for promotions, the surface humans and MCP agents curate through.

A revision is edited while it is a draft. Setting its status to informative or
executable publishes it through ``PromotionService``: the terms are validated,
hashed and frozen, or the revision stays a draft and the reasons are shown.
A published revision accepts only a status change; "Start a new revision"
copies it into an editable draft.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django import forms
from django.contrib import admin, messages
from django.db import models

from .models import (
    ActivationCode,
    CompatibilityRule,
    Promotion,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
    PurchaseRoute,
    RewardTerms,
)
from .services import PromotionService

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

PUBLISHING = (
    PromotionRevision.Status.INFORMATIVE,
    PromotionRevision.Status.EXECUTABLE,
)


class _FrozenWhenPublished:
    """Inline rows of a published revision are read-only."""

    def _editable(self, obj: PromotionRevision | None) -> bool:
        return obj is None or not obj.is_published

    def has_add_permission(
        self,
        request: HttpRequest,
        obj: PromotionRevision | None = None,
    ) -> bool:
        """Only a draft takes new rows."""
        return self._editable(obj) and super().has_add_permission(request, obj)

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: PromotionRevision | None = None,
    ) -> bool:
        """Only a draft's rows change."""
        return self._editable(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: PromotionRevision | None = None,
    ) -> bool:
        """Only a draft's rows go away."""
        return self._editable(obj) and super().has_delete_permission(request, obj)


class ActivationCodeInline(_FrozenWhenPublished, admin.TabularInline):
    """How a buyer activates the revision."""

    model = ActivationCode
    extra = 0


class PromotionScopeInline(_FrozenWhenPublished, admin.TabularInline):
    """What qualifies and what is targeted, included or excluded."""

    model = PromotionScope
    extra = 0


class PromotionEffectInline(_FrozenWhenPublished, admin.StackedInline):
    """What the revision grants."""

    model = PromotionEffect
    extra = 0


class CompatibilityRuleInline(_FrozenWhenPublished, admin.TabularInline):
    """Whether the revision combines with others."""

    model = CompatibilityRule
    extra = 0


class PromotionRevisionForm(forms.ModelForm):
    """Refuse a publication whose stored terms do not validate."""

    class Meta:
        """Form configuration."""

        model = PromotionRevision
        fields = (
            "promotion",
            "number",
            "status",
            "currency",
            "starts_at",
            "ends_at",
            "timezone",
            "verified_at",
            "review_by",
            "conditions",
            "ordering",
            "limitations",
            "evidence",
        )

    def clean(self) -> dict[str, object]:
        """Validate the terms already saved when the status publishes them."""
        cleaned = super().clean() or {}
        status = cleaned.get("status")
        revision = self.instance
        if revision.pk and not revision.is_published and status in PUBLISHING:
            for error in PromotionService().validate(revision, str(status)):
                self.add_error("status", error)
        if revision.pk and revision.is_published and status == "draft":
            self.add_error("status", "A published revision cannot return to draft.")
        return cleaned


@admin.register(PromotionRevision)
class PromotionRevisionAdmin(admin.ModelAdmin):
    """Edit a draft; publish, suspend or archive by status."""

    form = PromotionRevisionForm
    # One input per date: the JSON API merges a partial write field by field,
    # which a split date/time widget cannot round-trip.
    formfield_overrides: ClassVar[dict[type, dict[str, object]]] = {
        models.DateTimeField: {
            "form_class": forms.DateTimeField,
            "widget": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        },
    }
    list_display = ("__str__", "status", "starts_at", "ends_at", "verified_at")
    list_filter = ("status",)
    search_fields = ("promotion__title", "codes__code")
    filter_horizontal = ("evidence",)
    inlines = (
        ActivationCodeInline,
        PromotionScopeInline,
        PromotionEffectInline,
        CompatibilityRuleInline,
    )

    def get_readonly_fields(
        self,
        _request: HttpRequest,
        obj: PromotionRevision | None = None,
    ) -> tuple[str, ...]:
        """Show everything but the status of a published revision as read-only."""
        base = ("content_hash", "published_at")
        if obj is None or not obj.is_published:
            return base
        frozen = [
            name for name in PromotionRevisionForm.Meta.fields if name != "status"
        ]
        return (*base, *frozen)

    def save_model(
        self,
        request: HttpRequest,
        obj: PromotionRevision,
        form: forms.ModelForm,
        change: object,
    ) -> None:
        """Save a draft as a draft; move a published revision's status only."""
        target = obj.status
        if change and obj.is_published:
            PromotionService.set_status(obj, target)
            return
        request.publish_as = target if target in PUBLISHING else None
        obj.status = PromotionRevision.Status.DRAFT
        super().save_model(request, obj, form, change)

    def save_related(
        self,
        request: HttpRequest,
        form: forms.ModelForm,
        formsets: list[object],
        change: object,
    ) -> None:
        """Publish once every inline row is saved, or keep the draft and say why."""
        super().save_related(request, form, formsets, change)
        target = getattr(request, "publish_as", None)
        if target is None:
            return
        result = PromotionService().publish(form.instance, target)
        if not result.published:
            for error in result.errors:
                messages.error(request, f"Not published: {error}")


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    """A campaign's identity; its terms live in revisions."""

    list_display = ("title", "issuer_seller", "issuer_channel", "issuer_program")
    search_fields = ("title", "source_key")
    actions: ClassVar[list[str]] = ["start_revision"]

    @admin.action(description="Start a new revision")
    def start_revision(
        self,
        request: HttpRequest,
        queryset: QuerySet[Promotion],
    ) -> None:
        """Copy each promotion's latest revision into an editable draft."""
        service = PromotionService()
        for promotion in queryset:
            try:
                draft = service.revise(promotion)
            except ValueError as error:
                messages.error(request, f"{promotion}: {error}")
            else:
                messages.success(request, f"Started {draft}.")


@admin.register(RewardTerms)
class RewardTermsAdmin(admin.ModelAdmin):
    """How a cashback or points effect is credited."""

    list_display = ("__str__", "credited_as", "rate", "cap", "cap_period")
    list_filter = ("credited_as",)

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: RewardTerms | None = None,
    ) -> bool:
        """Terms of a published revision are read-only."""
        if obj is not None and obj.owning_revision().is_published:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: RewardTerms | None = None,
    ) -> bool:
        """Terms of a published revision stay."""
        if obj is not None and obj.owning_revision().is_published:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(PurchaseRoute)
class PurchaseRouteAdmin(admin.ModelAdmin):
    """How to buy an offer so the priced scenario holds."""

    list_display = ("__str__", "kind", "fixes_variant", "fixes_seller")
    list_filter = ("kind", "fixes_seller")
    filter_horizontal = ("compatible_programs",)
