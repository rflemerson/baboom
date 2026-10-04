"""R10: the combination search costs what its budget allows, never 2^n."""

from __future__ import annotations

import time
from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain.engine import evaluate
from pricing.domain.types import CompatibilityFact, OptimizationStatus
from pricing.tests.domain.builders import effect, inputs, policy, revision

ONE_SECOND = 1.0


def _promotions(count: int, *, compatible: bool) -> tuple:
    return tuple(
        revision(
            n,
            effect("percentage", basis="current", params={"rate": "1"}),
            compatibility=(
                tuple(
                    CompatibilityFact("promotion", str(other), "allowed")
                    for other in range(1, count + 1)
                    if other != n
                )
                if compatible
                else ()
            ),
        )
        for n in range(1, count + 1)
    )


class SearchBudgetTests(SimpleTestCase):
    """Incompatible promotions cost one node each; compatible ones are bounded."""

    def test_twenty_incompatible_promotions_are_searched_completely(self) -> None:
        """Twenty singletons and the empty set, not a million subsets."""
        started = time.perf_counter()
        result = evaluate(inputs(revisions=_promotions(20, compatible=False)))

        assert result.optimization_status == OptimizationStatus.COMPLETE
        assert result.merchandise_total == Decimal("99.00")
        assert time.perf_counter() - started < ONE_SECOND

    def test_hundreds_of_incompatible_promotions_stay_bounded(self) -> None:
        """Three hundred promotions and a budget of 256 nodes."""
        started = time.perf_counter()
        result = evaluate(inputs(revisions=_promotions(300, compatible=False)))

        assert result.optimization_status == OptimizationStatus.BOUNDED
        assert time.perf_counter() - started < ONE_SECOND * 5

    def test_thirty_compatible_promotions_never_enumerate_two_to_the_thirty(
        self,
    ) -> None:
        """Every subset is allowed; the budget stops the search and says so."""
        started = time.perf_counter()
        result = evaluate(
            inputs(
                revisions=_promotions(30, compatible=True),
                policy=policy(max_combinations=64),
            ),
        )

        assert result.optimization_status == OptimizationStatus.BOUNDED
        assert time.perf_counter() - started < ONE_SECOND * 5
