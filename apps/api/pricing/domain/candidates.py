"""Keep the promotion revisions that may apply to a cart in a scenario."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from promotions.rules.conditions import leaves
from promotions.rules.effects import (
    REWARD_EFFECTS,
    SUPPORTED_EFFECTS,
    unsupported_settings,
)

from .scopes import targets
from .types import (
    Decision,
    DecisionStatus,
)

if TYPE_CHECKING:
    from .effects import (
        LineState,
    )
    from .inputs import Inputs
    from .types import (
        Policy,
        RevisionRule,
    )


REWARD_KINDS = REWARD_EFFECTS


def candidate_revisions(
    inputs: Inputs,
    lines: list[LineState],
    decisions: list[Decision],
) -> list[RevisionRule]:
    """Keep the revisions that may apply to these lines in this scenario."""
    context, policy = inputs.context, inputs.policy
    kept: list[RevisionRule] = []
    for revision in sorted(inputs.revisions, key=lambda item: item.id):
        subject = f"revision {revision.id}"
        if not policy.apply_benefits:
            decisions.append(
                Decision(subject, DecisionStatus.INELIGIBLE, "scenario applies none"),
            )
            continue
        reason = static_refusal(revision, inputs, lines)
        if reason is not None:
            status, text = reason
            decisions.append(Decision(subject, status, text))
            continue
        if revision.starts_at and context.now < revision.starts_at:
            decisions.append(
                Decision(subject, DecisionStatus.INELIGIBLE, "not started")
            )
            continue
        if revision.ends_at and context.now >= revision.ends_at:
            decisions.append(Decision(subject, DecisionStatus.INELIGIBLE, "ended"))
            continue
        effective = revision
        if not policy.allow_rewards:
            effective = replace(
                revision,
                effects=tuple(
                    e for e in revision.effects if e.kind not in REWARD_KINDS
                ),
            )
            if not effective.effects:
                decisions.append(
                    Decision(
                        subject, DecisionStatus.INELIGIBLE, "scenario excludes rewards"
                    ),
                )
                continue
        kept.append(effective)
    return kept


def static_refusal(
    revision: RevisionRule,
    inputs: Inputs,
    lines: list[LineState],
) -> tuple[DecisionStatus, str] | None:
    """Return why a revision cannot apply before any arithmetic, or None."""
    checks = (
        _status_refusal(revision, inputs),
        _terms_refusal(revision, inputs.policy),
        _reach_refusal(revision, lines, len(inputs.context.groups)),
    )
    return next((refusal for refusal in checks if refusal is not None), None)


def _status_refusal(
    revision: RevisionRule,
    inputs: Inputs,
) -> tuple[DecisionStatus, str] | None:
    """Refuse a revision not executable, or in another currency."""
    if revision.status == "informative":
        return DecisionStatus.INFORMATIVE, "terms not sufficient to compute"
    if revision.status != "executable":
        return DecisionStatus.INELIGIBLE, f"revision is {revision.status}"
    if revision.currency != inputs.context.currency:
        return DecisionStatus.UNSUPPORTED, "terms in another currency"
    unsupported = [e.kind for e in revision.effects if e.kind not in SUPPORTED_EFFECTS]
    if unsupported:
        return DecisionStatus.UNSUPPORTED, f"effects {unsupported} not computed"
    limits = [problem for e in revision.effects for problem in unsupported_settings(e)]
    if limits:
        return DecisionStatus.UNSUPPORTED, "; ".join(limits)
    return None


def _terms_refusal(
    revision: RevisionRule,
    policy: Policy,
) -> tuple[DecisionStatus, str] | None:
    """Refuse terms the scenario does not count: codes or excluded conditions."""
    code_kinds = {kind for kind, _code in revision.codes}
    if code_kinds & {"public_code", "personal_code"} and not policy.allow_codes:
        return DecisionStatus.INELIGIBLE, "scenario excludes codes"
    if "personal_code" in code_kinds and not policy.allow_private_codes:
        return DecisionStatus.INELIGIBLE, "personal code"
    excluded = sorted(
        kind
        for kind in _leaf_kinds(revision.conditions.get("root"))
        if kind not in policy.allow_conditions and kind != "code_required"
    )
    if excluded:
        return DecisionStatus.INELIGIBLE, f"scenario excludes {excluded}"
    return None


GROUP_TARGETS = frozenset({"order", "group"})


GROUP_SCOPES = frozenset({"checkout_group", "seller"})


def _per_group(revision: RevisionRule) -> bool:
    """Tell whether a revision's terms depend on how lines are grouped."""
    if any(
        effect.target in GROUP_TARGETS or effect.basis == "order_total"
        for effect in revision.effects
    ):
        return True
    root = revision.conditions.get("root")
    return any(
        isinstance(leaf, dict) and leaf.get("scope") in GROUP_SCOPES
        for leaf in _leaves(root)
    )


def _leaves(node: object) -> list[dict]:
    return list(leaves(node))


def _reach_refusal(
    revision: RevisionRule,
    lines: list[LineState],
    groups: int = 1,
) -> tuple[DecisionStatus, str] | None:
    """Refuse a revision that reaches no line, or repeats an included discount.

    With several checkout groups, terms that depend on the order or group
    are not evaluated per group yet: they are unsupported, never applied to
    the whole cart as if it were one order.
    """
    if groups > 1 and _per_group(revision):
        return (
            DecisionStatus.UNSUPPORTED,
            "order-level terms across several checkout groups",
        )
    if not any(targets(revision, line.offer) for line in lines):
        return DecisionStatus.INELIGIBLE, "targets none of these offers"
    if _payment_already_included(revision, lines):
        return DecisionStatus.CONFLICT, "payment discount already in the price"
    return None


def _leaf_kinds(node: object) -> set[str]:
    return {str(leaf.get("kind")) for leaf in leaves(node)}


def _payment_already_included(revision: RevisionRule, lines: list[LineState]) -> bool:
    """Tell whether a payment discount would repeat one already in the price."""
    payment_effects = [e for e in revision.effects if e.stage == "payment"]
    if not payment_effects:
        return False
    targeted = [line for line in lines if targets(revision, line.offer)]
    return bool(targeted) and all(
        "payment_discount" in line.price.already_included for line in targeted
    )
