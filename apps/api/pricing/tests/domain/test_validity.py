"""SYNTHETIC: a result is valid only for what its own alternative used."""

from __future__ import annotations

from datetime import timedelta

from django.test import SimpleTestCase

from pricing.domain.engine import evaluate
from pricing.tests.domain.builders import (
    NOW,
    effect,
    inputs,
    policy,
    price,
    revision,
)

TEN_PERCENT = effect("percentage", params={"rate": "10"})


class ValidityTests(SimpleTestCase):
    """A base price holds until the next read; promotions bound the rest."""

    def test_a_price_without_promotions_never_expires(self) -> None:
        """The next crawl replaces it; time alone does not."""
        result = evaluate(inputs(prices=(price(1, "100.00"),)))

        assert result.expires_at is None

    def test_the_normal_policy_ignores_promotions_when_expiring(self) -> None:
        """A promotion starting in five minutes changes nothing it applies."""
        result = evaluate(
            inputs(
                revisions=(
                    revision(7, TEN_PERCENT, starts_at=NOW + timedelta(minutes=5)),
                ),
                policy=policy("listed", apply_benefits=False),
            ),
        )

        assert result.expires_at is None

    def test_a_future_promotion_shortens_a_policy_that_applies_benefits(self) -> None:
        """It could lower the price, so the result ends when it starts."""
        start = NOW + timedelta(minutes=5)
        result = evaluate(
            inputs(revisions=(revision(7, TEN_PERCENT, starts_at=start),))
        )

        assert result.expires_at == start

    def test_an_ended_unapplied_promotion_does_not_matter(self) -> None:
        """The end of a promotion the result did not use changes nothing."""
        result = evaluate(
            inputs(
                revisions=(
                    revision(
                        7,
                        effect("percentage", params={"rate": "10"}),
                        conditions={
                            "root": {
                                "kind": "min_amount",
                                "amount": "500",
                                "currency": "BRL",
                                "basis": "before_discounts",
                                "scope": "order",
                            },
                        },
                        ends_at=NOW + timedelta(minutes=5),
                    ),
                ),
            ),
        )

        assert result.applied_revisions == ()
        assert result.expires_at is None
