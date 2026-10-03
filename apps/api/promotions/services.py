"""Validate, publish and revise promotion revisions.

The admin, its JSON API (and therefore MCP) and any job publish through
``PromotionService``. Publishing validates the whole revision, fixes the hash
of its canonical content and freezes it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.apps import apps
from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError as SchemaError

from .models import (
    ActivationCode,
    CompatibilityRule,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
    RewardTerms,
)
from .schemas import (
    EFFECT_PARAMS,
    MONETARY_EFFECTS,
    ORDERING,
    ChannelIn,
    ConditionTree,
    MarketIn,
    NewCustomer,
    ProgramMember,
    SellerIn,
    leaves,
)

if TYPE_CHECKING:
    from django.db.models import Model

    from .models import Promotion

SCOPE_MODELS = {
    "channel": "commerce.Channel",
    "market": "commerce.Market",
    "seller_account": "commerce.SellerAccount",
    "merchant": "commerce.Merchant",
    "brand": "core.Brand",
    "category": "core.Category",
    "product": "core.Product",
    "listing": "offers.Listing",
    "listing_variant": "offers.ListingVariant",
    "offer": "offers.Offer",
}
NEW_CUSTOMER_ISSUERS = {
    "channel": "commerce.Channel",
    "seller": "commerce.SellerAccount",
    "program": "commerce.Program",
}
# Effects whose computation needs reward terms.
REWARD_EFFECTS = frozenset({"cashback", "points"})


@dataclass(frozen=True)
class PublishResult:
    """Whether a revision was published, and why not."""

    published: bool
    errors: tuple[str, ...]


def _exists(label: str, ids: list[int]) -> list[int]:
    """Return the ids among ``ids`` that do not exist in the model ``label``."""
    model: type[Model] = apps.get_model(label)
    found = set(model.objects.filter(pk__in=ids).values_list("pk", flat=True))
    return [pk for pk in ids if pk not in found]


class PromotionService:
    """The one path to publish or revise a promotion's terms."""

    # Validation

    def validate(self, revision: PromotionRevision, status: str) -> list[str]:
        """Return why ``revision`` cannot be published with ``status``."""
        errors = self._conditions(revision)
        effects = list(revision.effects.select_related("reward_terms"))
        errors += self._effects(revision, effects)
        errors += self._ordering(revision, effects)
        errors += self._scopes(revision)
        errors += self._codes(revision)
        errors += self._compatibility(revision)
        if status == PromotionRevision.Status.EXECUTABLE:
            errors += self._executable(revision, effects)
        return errors

    @staticmethod
    def _conditions(revision: PromotionRevision) -> list[str]:
        try:
            tree = ConditionTree.model_validate(revision.conditions or {})
        except SchemaError as error:
            return [f"Conditions: {error.errors()[0]['msg']}"]
        errors: list[str] = []
        for leaf in leaves(tree.root):
            if isinstance(leaf, ChannelIn):
                missing = _exists("commerce.Channel", leaf.channel_ids)
            elif isinstance(leaf, MarketIn):
                missing = _exists("commerce.Market", leaf.market_ids)
            elif isinstance(leaf, SellerIn):
                missing = _exists("commerce.SellerAccount", leaf.seller_account_ids)
            elif isinstance(leaf, ProgramMember):
                missing = _exists("commerce.Program", [leaf.program_id])
            elif isinstance(leaf, NewCustomer):
                label = NEW_CUSTOMER_ISSUERS[leaf.issuer]
                missing = _exists(label, [leaf.issuer_id])
            else:
                missing = []
            if missing:
                errors.append(f"Conditions name missing {leaf.kind} ids {missing}.")
            amount_currency = getattr(leaf, "currency", None)
            if amount_currency and amount_currency != revision.currency_id:
                errors.append(
                    f"A minimum in {amount_currency} in terms of "
                    f"{revision.currency_id}.",
                )
        return errors

    @staticmethod
    def _effects(
        revision: PromotionRevision,
        effects: list[PromotionEffect],
    ) -> list[str]:
        errors: list[str] = []
        for effect in effects:
            schema = EFFECT_PARAMS[effect.kind]
            try:
                schema.model_validate(effect.parameters or {})
            except SchemaError as error:
                errors.append(f"Effect {effect}: {error.errors()[0]['msg']}")
            if effect.kind in REWARD_EFFECTS and effect.stage != "reward":
                errors.append(f"Effect {effect}: a reward applies at the reward stage.")
            if effect.kind not in REWARD_EFFECTS and effect.stage == "reward":
                errors.append(f"Effect {effect}: only rewards use the reward stage.")
            if effect.kind == "shipping_discount" and effect.target != "shipping":
                errors.append(f"Effect {effect}: a shipping discount targets shipping.")
            if effect.kind in MONETARY_EFFECTS and not revision.currency_id:
                errors.append(f"Effect {effect}: a fixed value needs a currency.")
        return errors

    @staticmethod
    def _ordering(
        revision: PromotionRevision,
        effects: list[PromotionEffect],
    ) -> list[str]:
        try:
            edges = ORDERING.validate_python(revision.ordering or [])
        except SchemaError as error:
            return [f"Precedence: {error.errors()[0]['msg']}"]
        positions = {effect.position for effect in effects}
        unknown = sorted(
            {p for edge in edges for p in (edge.before, edge.after)} - positions,
        )
        if unknown:
            return [f"Precedence names effects that do not exist: {unknown}."]
        graph = {position: set() for position in positions}
        for edge in edges:
            graph[edge.before].add(edge.after)
        if _has_cycle(graph):
            return ["Precedence has a cycle: no effect can be computed first."]
        return []

    @staticmethod
    def _scopes(revision: PromotionRevision) -> list[str]:
        errors: list[str] = []
        for scope in revision.scopes.all():
            label = SCOPE_MODELS.get(scope.kind)
            if label and scope.ref_id is not None and _exists(label, [scope.ref_id]):
                errors.append(f"Scope {scope}: no {scope.kind} #{scope.ref_id}.")
        return errors

    @staticmethod
    def _codes(revision: PromotionRevision) -> list[str]:
        codes = [code.code for code in revision.codes.all() if code.code]
        if len(codes) != len(set(codes)):
            return ["A code appears twice in one revision."]
        return []

    @staticmethod
    def _compatibility(revision: PromotionRevision) -> list[str]:
        """Refuse a rule that contradicts a published rule of the other side."""
        errors: list[str] = []
        own = str(revision.promotion_id)
        for rule in revision.compatibility.filter(other_kind="promotion"):
            opposite = CompatibilityRule.objects.filter(
                revision__promotion_id=rule.other_ref,
                revision__status__in=("executable", "informative"),
                other_kind="promotion",
                other_ref=own,
            ).exclude(verdict__in=(rule.verdict, "unknown"))
            if rule.verdict != "unknown" and opposite.exists():
                errors.append(
                    f"Promotion {rule.other_ref} says the opposite about combining "
                    f"with this one; resolve it before publishing.",
                )
        return errors

    @staticmethod
    def _executable(
        revision: PromotionRevision,
        effects: list[PromotionEffect],
    ) -> list[str]:
        """Require effects, complete rewards, a target and evidence to compute."""
        errors: list[str] = []
        if not effects:
            errors.append("An executable revision grants at least one effect.")
        for effect in effects:
            if effect.kind not in REWARD_EFFECTS:
                continue
            terms = getattr(effect, "reward_terms", None)
            if terms is None:
                errors.append(f"Effect {effect}: a reward needs its reward terms.")
            elif effect.kind == "cashback" and terms.rate is None:
                errors.append(f"Effect {effect}: cashback needs its rate.")
        if not revision.scopes.filter(role=PromotionScope.Role.TARGET).exists():
            errors.append("An executable revision names what it targets.")
        if not revision.evidence.exists():
            errors.append("An executable revision rests on evidence.")
        return errors

    # Publication

    @transaction.atomic
    def publish(self, revision: PromotionRevision, status: str) -> PublishResult:
        """Validate, hash and freeze a draft as informative or executable."""
        if status not in (
            PromotionRevision.Status.INFORMATIVE,
            PromotionRevision.Status.EXECUTABLE,
        ):
            return PublishResult(
                published=False, errors=(f"Cannot publish as {status}.",)
            )
        locked = PromotionRevision.objects.select_for_update().get(pk=revision.pk)
        if locked.is_published:
            return PublishResult(
                published=False,
                errors=("The revision is already published.",),
            )
        errors = self.validate(locked, status)
        if errors:
            return PublishResult(published=False, errors=tuple(errors))
        locked.status = status
        locked.published_at = timezone.now()
        locked.content_hash = content_hash(locked)
        PromotionRevision.objects.filter(pk=locked.pk).update(
            status=locked.status,
            published_at=locked.published_at,
            content_hash=locked.content_hash,
            updated_at=locked.published_at,
        )
        revision.refresh_from_db()
        return PublishResult(published=True, errors=())

    @staticmethod
    def set_status(revision: PromotionRevision, status: str) -> None:
        """Suspend, archive or resume a published revision; nothing else changes."""
        allowed = PromotionRevision.PUBLISHED
        if not revision.is_published or status not in allowed:
            msg = f"A published revision moves only among {sorted(allowed)}."
            raise ValueError(msg)
        PromotionRevision.objects.filter(pk=revision.pk).update(
            status=status,
            updated_at=timezone.now(),
        )
        revision.refresh_from_db()

    @transaction.atomic
    def revise(self, promotion: Promotion) -> PromotionRevision:
        """Start a draft copying the latest revision, to edit and publish anew."""
        latest = promotion.revisions.order_by("-number").first()
        if latest is None:
            msg = "A promotion's first revision is created directly."
            raise ValueError(msg)
        draft = PromotionRevision.objects.create(
            promotion=promotion,
            number=latest.number + 1,
            currency=latest.currency,
            starts_at=latest.starts_at,
            ends_at=latest.ends_at,
            timezone=latest.timezone,
            verified_at=latest.verified_at,
            review_by=latest.review_by,
            conditions=latest.conditions,
            ordering=latest.ordering,
            limitations=latest.limitations,
        )
        draft.evidence.set(latest.evidence.all())
        for code in latest.codes.all():
            ActivationCode.objects.create(
                revision=draft,
                kind=code.kind,
                code=code.code,
                channel_scope=code.channel_scope,
                instructions=code.instructions,
            )
        for scope in latest.scopes.all():
            PromotionScope.objects.create(
                revision=draft,
                role=scope.role,
                mode=scope.mode,
                kind=scope.kind,
                ref_id=scope.ref_id,
                external_ref=scope.external_ref,
                combine=scope.combine,
            )
        for effect in latest.effects.all():
            terms = getattr(effect, "reward_terms", None)
            copy = PromotionEffect.objects.create(
                revision=draft,
                **{field: getattr(effect, field) for field in _EFFECT_FIELDS},
            )
            if terms is not None:
                RewardTerms.objects.create(
                    effect=copy,
                    **{field: getattr(terms, field) for field in _REWARD_FIELDS},
                )
        for rule in latest.compatibility.all():
            CompatibilityRule.objects.create(
                revision=draft,
                other_kind=rule.other_kind,
                other_ref=rule.other_ref,
                verdict=rule.verdict,
                chooser=rule.chooser,
                evidence=rule.evidence,
            )
        return draft


_EFFECT_FIELDS = (
    "position",
    "kind",
    "stage",
    "basis",
    "target",
    "allocation",
    "parameters",
    "cap",
    "max_applications",
    "consumes_units",
)
_REWARD_FIELDS = (
    "program_id",
    "credited_as",
    "eligible_basis",
    "includes_shipping",
    "rate",
    "cap",
    "cap_period",
    "minimum",
    "tracking_required",
    "credit_delay_days",
    "delay_from",
    "expires_after_days",
    "redemption_minimum",
    "cancellation_terms",
)


def _has_cycle(graph: dict[int, set[int]]) -> bool:
    """Whether a directed graph has a cycle (Kahn's algorithm)."""
    incoming = dict.fromkeys(graph, 0)
    for targets in graph.values():
        for target in targets:
            incoming[target] += 1
    ready = [node for node, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for target in graph[node]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    return visited != len(graph)


def snapshot(revision: PromotionRevision) -> dict[str, object]:
    """Return the canonical content of a revision and everything it owns."""
    return {
        "promotion": revision.promotion_id,
        "number": revision.number,
        "currency": revision.currency_id,
        "starts_at": revision.starts_at.isoformat() if revision.starts_at else None,
        "ends_at": revision.ends_at.isoformat() if revision.ends_at else None,
        "timezone": revision.timezone,
        "conditions": revision.conditions,
        "ordering": revision.ordering,
        "limitations": revision.limitations,
        "evidence": sorted(revision.evidence.values_list("pk", flat=True)),
        "codes": sorted(
            [code.kind, code.code, code.channel_scope] for code in revision.codes.all()
        ),
        "scopes": sorted(
            [s.role, s.mode, s.kind, s.ref_id or 0, s.external_ref, s.combine]
            for s in revision.scopes.all()
        ),
        "effects": [
            {
                **{field: str(getattr(effect, field)) for field in _EFFECT_FIELDS},
                "reward": (
                    {
                        field: str(getattr(effect.reward_terms, field))
                        for field in _REWARD_FIELDS
                    }
                    if hasattr(effect, "reward_terms")
                    else None
                ),
            }
            for effect in revision.effects.order_by("position")
        ],
        "compatibility": sorted(
            [rule.other_kind, rule.other_ref, rule.verdict, rule.chooser]
            for rule in revision.compatibility.all()
        ),
    }


def content_hash(revision: PromotionRevision) -> str:
    """Hash a revision's canonical content."""
    canonical = json.dumps(snapshot(revision), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
