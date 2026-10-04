"""The effect by parameter matrix: what the engine honours, publication enforces."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain import effects
from pricing.domain.engine import evaluate
from pricing.domain.types import CartLine, DecisionStatus, PaymentChoice
from pricing.tests.domain.builders import (
    context,
    effect,
    inputs,
    offer,
    policy,
    price,
    revision,
)
from promotions import schemas


class MatrixTests(SimpleTestCase):
    """The validator and the engine agree on every limit."""

    def test_both_sides_list_the_same_kinds(self) -> None:
        """A limit is honoured by the engine exactly where publication allows it."""
        assert effects.CAPPED_EFFECTS == schemas.CAPPED_EFFECTS
        assert effects.LIMITED_EFFECTS == schemas.LIMITED_EFFECTS
        assert frozenset(schemas.EFFECT_PARAMS) == effects.SUPPORTED_EFFECTS

    def test_an_ignored_limit_makes_the_revision_unsupported(self) -> None:
        """A gift with a cap is not silently uncapped."""
        promo = revision(1, effect("gift", params={"quantity": 1}, cap=Decimal(5)))

        result = evaluate(inputs(revisions=(promo,)))

        assert DecisionStatus.UNSUPPORTED in {d.status for d in result.decisions}


class ReviewCalculationTests(SimpleTestCase):
    """R07, R09 and R12, beyond the reviewer's single cases."""

    def test_multibuy_cap_is_allocated_over_the_free_units(self) -> None:
        """Buy 3 pay 2 on R$ 100 units, capped at R$ 10: R$ 290."""
        promo = revision(
            1,
            effect("multibuy", params={"buy": 3, "pay": 2}, cap=Decimal(10)),
        )

        result = evaluate(inputs(context=context(CartLine(1, 3)), revisions=(promo,)))

        assert result.merchandise_total == Decimal("290.00")
        assert result.adjustments[0].amount == Decimal("10.00")

    def test_a_payment_discount_reaches_only_lines_without_one(self) -> None:
        """A (Pix, includes it) stays 90; B gets 10%: 180, and the reason is kept."""
        promo = revision(
            1, effect("percentage", stage="payment", params={"rate": "10"})
        )
        result = evaluate(
            inputs(
                context=context(CartLine(1), CartLine(2)),
                offers=(offer(1), offer(2)),
                prices=(
                    price(1, "90", included_adjustments=("payment_discount",)),
                    price(2, "100"),
                ),
                revisions=(promo,),
            ),
        )

        assert result.merchandise_total == Decimal("180.00")
        assert result.adjustments[0].allocations == ((2, Decimal("10.00")),)
        assert any("not applied to them" in d.reason for d in result.decisions)

    def test_every_payment_scope_in_every_scenario(self) -> None:
        """any: listed, cash and one payment; never an installment plan."""
        universal = (price(1, "100", payment_scope="any"),)
        expected = {
            ("listed", None): Decimal("100.00"),
            ("cash", None): Decimal("100.00"),
            ("payment", PaymentChoice("credit_card", 1)): Decimal("100.00"),
            ("payment", PaymentChoice("credit_card", 3)): None,
        }
        for (scenario, payment), total in expected.items():
            with self.subTest(scenario=scenario, payment=payment):
                data = inputs(prices=universal, policy=policy(scenario))
                data = replace(data, context=replace(data.context, payment=payment))
                assert evaluate(data).merchandise_total == total
