"""Enumerate the combinations compatibility allows, within the search budget."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .types import (
    Decision,
    DecisionStatus,
    OptimizationStatus,
)

if TYPE_CHECKING:
    from .types import (
        CompatibilityFact,
        Policy,
        RevisionRule,
    )


def _names(rule: CompatibilityFact, other: RevisionRule) -> bool:
    """Tell whether a compatibility rule is about another revision."""
    if rule.other_kind == "promotion":
        return rule.other_ref == str(other.promotion_id)
    if rule.other_kind == "effect_kind":
        return rule.other_ref in {effect.kind for effect in other.effects}
    return False


def _compatible(first: RevisionRule, second: RevisionRule) -> tuple[bool, str]:
    """Whether two revisions combine, and who decides when they do not."""
    verdicts = [
        (rule.verdict, rule.chooser)
        for own, other in ((first, second), (second, first))
        for rule in own.compatibility
        if _names(rule, other)
    ]
    if any(verdict == "forbidden" for verdict, _ in verdicts):
        chooser = next(c for v, c in verdicts if v == "forbidden")
        return False, chooser
    if any(verdict == "allowed" for verdict, _ in verdicts):
        return True, ""
    return False, "buyer_choice"


def combinations(
    candidates: list[RevisionRule],
    policy: Policy,
    decisions: list[Decision],
    assumptions: list[str],
) -> tuple[list[tuple[RevisionRule, ...]], OptimizationStatus]:
    """Return the pairwise-compatible subsets, within a budget of visited nodes.

    The search grows a subset only with candidates compatible with every
    member, so incompatible promotions cost one node each instead of an
    exponential enumeration. ``max_combinations`` bounds the nodes visited;
    when the search stops early the result says ``bounded``.
    """
    store_pairs: list[tuple[int, int]] = []
    neighbours: dict[int, set[int]] = {index: set() for index in range(len(candidates))}
    for i, j in itertools.combinations(range(len(candidates)), 2):
        ok, chooser = _compatible(candidates[i], candidates[j])
        if ok:
            neighbours[i].add(j)
        elif chooser == "store_imposed":
            store_pairs.append((candidates[i].id, candidates[j].id))
    for first_id, second_id in store_pairs:
        decisions.append(
            Decision(
                f"revisions {first_id} and {second_id}",
                DecisionStatus.CONFLICT,
                "the store chooses one",
            ),
        )
    dropped = _store_choice(store_pairs, assumptions)
    allowed = {i for i, c in enumerate(candidates) if c.id not in dropped}
    search = _Search(candidates, neighbours, policy.max_combinations)
    search.grow((), allowed)
    status = (
        OptimizationStatus.BOUNDED if search.stopped else OptimizationStatus.COMPLETE
    )
    return search.subsets, status


@dataclass
class _Search:
    """A depth-first search over compatible subsets, with a node budget."""

    candidates: list[RevisionRule]
    neighbours: dict[int, set[int]]
    budget: int
    subsets: list[tuple[RevisionRule, ...]] = field(default_factory=lambda: [()])
    visited: int = 1
    stopped: bool = False

    def grow(self, members: tuple[int, ...], options: set[int]) -> None:
        """Extend a subset with each option compatible with all its members."""
        for index in sorted(options):
            if members and index < members[-1]:
                continue
            if self.visited >= self.budget:
                self.stopped = True
                return
            self.visited += 1
            subset = (*members, index)
            self.subsets.append(tuple(self.candidates[i] for i in subset))
            self.grow(subset, options & self.neighbours[index])
            if self.stopped:
                return


def _store_choice(
    store_pairs: list[tuple[int, int]],
    assumptions: list[str],
) -> set[int]:
    """Return the revisions dropped where the store picks between two.

    The store's choice is not known; the revision published first is assumed,
    and the assumption is reported.
    """
    assumptions.extend(
        f"the store's choice between revisions {a} and {b} assumed to be {min(a, b)}"
        for a, b in store_pairs
    )
    return {max(pair) for pair in store_pairs}
