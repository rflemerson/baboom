"""One framework-free registry of what each effect kind's handler applies.

Publication (admin and MCP) and calculation read the same ``EFFECT_SPECS``:
a setting a handler would ignore cannot be published as executable, and an
unpublishable rule that exists anyway is unsupported at calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from decimal import Decimal

DISCOUNT_STAGES = frozenset({"catalog", "order", "payment"})
ITEM_TARGETS = frozenset({"item", "line", "group", "order"})


@dataclass(frozen=True)
class EffectSpec:
    """The settings a handler honours for one effect kind.

    ``limit_allocations`` names the allocations under which an application
    limit means something; elsewhere a limit would be ignored.
    """

    stages: frozenset[str]
    targets: frozenset[str]
    bases: frozenset[str]
    allocations: frozenset[str]
    cap: bool = False
    application_limit: bool = False
    limit_allocations: frozenset[str] = field(default_factory=frozenset)


EFFECT_SPECS: dict[str, EffectSpec] = {
    # A rate gives each line the same share whatever the allocation names.
    "percentage": EffectSpec(
        stages=DISCOUNT_STAGES,
        targets=ITEM_TARGETS,
        bases=frozenset({"initial", "current", "eligible_subtotal", "order_total"}),
        allocations=frozenset({"prorated", "once", "per_line", "per_unit"}),
        cap=True,
    ),
    "fixed_amount": EffectSpec(
        stages=DISCOUNT_STAGES,
        targets=ITEM_TARGETS,
        bases=frozenset({"current", "eligible_subtotal"}),
        allocations=frozenset({"per_unit", "per_line", "once", "prorated"}),
        cap=True,
        application_limit=True,
        limit_allocations=frozenset({"per_unit", "per_line"}),
    ),
    "fixed_price": EffectSpec(
        stages=DISCOUNT_STAGES,
        targets=ITEM_TARGETS,
        bases=frozenset({"current"}),
        allocations=frozenset({"per_unit"}),
        cap=True,
    ),
    "multibuy": EffectSpec(
        stages=frozenset({"catalog", "order"}),
        targets=ITEM_TARGETS,
        bases=frozenset({"current"}),
        allocations=frozenset({"per_unit", "prorated"}),
        cap=True,
        application_limit=True,
        limit_allocations=frozenset({"per_unit", "prorated"}),
    ),
    "tiered": EffectSpec(
        stages=frozenset({"catalog", "order"}),
        targets=ITEM_TARGETS,
        bases=frozenset({"current", "eligible_subtotal"}),
        allocations=frozenset({"prorated", "per_unit", "per_line"}),
        cap=True,
    ),
    "subscription": EffectSpec(
        stages=frozenset({"catalog"}),
        targets=ITEM_TARGETS,
        bases=frozenset({"current"}),
        allocations=frozenset({"prorated"}),
        cap=True,
    ),
    "shipping_discount": EffectSpec(
        stages=frozenset({"shipping"}),
        targets=frozenset({"shipping"}),
        bases=frozenset({"component"}),
        allocations=frozenset({"once"}),
        cap=True,
    ),
    "cashback": EffectSpec(
        stages=frozenset({"reward"}),
        targets=ITEM_TARGETS,
        bases=frozenset({"eligible_subtotal"}),
        allocations=frozenset({"once"}),
    ),
    "points": EffectSpec(
        stages=frozenset({"reward"}),
        targets=ITEM_TARGETS,
        bases=frozenset({"eligible_subtotal"}),
        allocations=frozenset({"once"}),
    ),
    "gift": EffectSpec(
        stages=frozenset({"catalog", "order"}),
        targets=ITEM_TARGETS,
        bases=frozenset({"current", "eligible_subtotal"}),
        allocations=frozenset({"once"}),
    ),
}
CAPPED_EFFECTS = frozenset(kind for kind, spec in EFFECT_SPECS.items() if spec.cap)
LIMITED_EFFECTS = frozenset(
    kind for kind, spec in EFFECT_SPECS.items() if spec.application_limit
)
SUPPORTED_EFFECTS = frozenset(EFFECT_SPECS)
REWARD_EFFECTS = frozenset(
    kind for kind, spec in EFFECT_SPECS.items() if spec.stages == {"reward"}
)


class EffectSettings(Protocol):
    """The common surface of persisted rules and immutable engine rules."""

    kind: str
    stage: str
    target: str
    basis: str
    allocation: str
    cap: Decimal | None
    max_applications: int | None


def unsupported_settings(effect: EffectSettings) -> list[str]:
    """Return the settings of an effect its handler would not apply."""
    spec = EFFECT_SPECS.get(effect.kind)
    if spec is None:
        return [f"unsupported effect {effect.kind}"]
    problems: list[str] = []
    for name, value, allowed in (
        ("stage", effect.stage, spec.stages),
        ("target", effect.target, spec.targets),
        ("basis", effect.basis, spec.bases),
        ("allocation", effect.allocation, spec.allocations),
    ):
        if value not in allowed:
            problems.append(
                f"{effect.kind} takes {name} {sorted(allowed)}, not {value!r}",
            )
    if effect.cap is not None and not spec.cap:
        problems.append(f"{effect.kind} takes no cap")
    if effect.max_applications is not None and (
        not spec.application_limit or effect.allocation not in spec.limit_allocations
    ):
        problems.append(
            f"{effect.kind} takes no application limit with allocation "
            f"{effect.allocation!r}",
        )
    return problems
