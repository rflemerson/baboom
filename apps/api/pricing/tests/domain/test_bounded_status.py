"""SYNTHETIC: a result says "bounded" whenever any part of the search was cut."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain.engine import evaluate
from pricing.domain.types import OptimizationStatus
from pricing.tests.domain.builders import effect, inputs, policy, price, revision


def _bases(count: int) -> tuple:
    """Distinct base prices of one offer: each already includes another thing."""
    return tuple(
        price(
            1,
            f"{100 + n}.00",
            payment_scope="any",
            included_adjustments=(f"synthetic_{n}",),
        )
        for n in range(count)
    )


class BoundedStatusTests(SimpleTestCase):
    """Cut bases, payments, candidates or combinations are declared."""

    def test_seventeen_distinct_bases_are_bounded(self) -> None:
        """More than the base budget: only each line's cheapest is searched."""
        result = evaluate(inputs(prices=_bases(17)))

        assert result.optimization_status == OptimizationStatus.BOUNDED
        assert result.merchandise_total == Decimal("100.00")

    def test_sixteen_distinct_bases_are_complete(self) -> None:
        """Exactly the base budget is still searched completely."""
        result = evaluate(inputs(prices=_bases(16)))

        assert result.optimization_status == OptimizationStatus.COMPLETE

    def test_more_promotions_than_are_compared_are_bounded(self) -> None:
        """Pairs are compared only for the first 64 by id; the rest is declared."""
        promotions = tuple(
            revision(n, effect("percentage", params={"rate": "1"}))
            for n in range(1, 70)
        )

        result = evaluate(inputs(revisions=promotions))

        assert result.optimization_status == OptimizationStatus.BOUNDED
        assert result.merchandise_total == Decimal("99.00")
        assert any(
            d.reason == "beyond the number of promotions compared"
            for d in result.decisions
        )

    def test_a_search_cut_without_a_winner_is_bounded_not_complete(self) -> None:
        """A search cut before a winner differs from nothing being eligible."""
        wants_coupon = frozenset({"coupon"})

        cut = evaluate(inputs(prices=_bases(17), benefits=wants_coupon))
        covered = evaluate(inputs(benefits=wants_coupon))

        assert cut.merchandise_total is None
        assert cut.optimization_status == OptimizationStatus.BOUNDED
        assert covered.merchandise_total is None
        assert covered.optimization_status == OptimizationStatus.COMPLETE

    def test_no_usable_price_is_complete(self) -> None:
        """Nothing to search: no eligible alternative exists."""
        result = evaluate(inputs(prices=()))

        assert result.merchandise_total is None
        assert result.optimization_status == OptimizationStatus.COMPLETE

    def test_a_budget_spent_across_bases_is_bounded(self) -> None:
        """A budget of one node cannot cover two bases with a promotion."""
        result = evaluate(
            replace(
                inputs(
                    prices=_bases(2),
                    revisions=(revision(7, effect("percentage")),),
                ),
                policy=policy("best", max_combinations=1),
            ),
        )

        assert result.optimization_status == OptimizationStatus.BOUNDED
