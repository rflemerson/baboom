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
from pricing_contracts.effects import EFFECT_SPECS, unsupported_settings
from promotions import schemas


class MatrixTests(SimpleTestCase):
    """One registry decides; every allowed setting computes, every other is refused."""

    def test_every_kind_has_a_handler_and_a_parameter_schema(self) -> None:
        """No kind is publishable without a handler, nor computable without a spec."""
        assert set(effects.HANDLERS) == set(EFFECT_SPECS)
        assert set(schemas.EFFECT_PARAMS) == set(EFFECT_SPECS)

    def test_each_allowed_setting_is_supported_and_each_other_refused(self) -> None:
        """The engine and publication read the same answer for every setting."""
        values = {
            "stage": ("catalog", "order", "payment", "shipping", "reward"),
            "target": ("item", "line", "group", "order", "shipping"),
            "basis": (
                "initial",
                "current",
                "eligible_subtotal",
                "order_total",
                "component",
            ),
            "allocation": ("per_unit", "per_line", "once", "prorated"),
        }
        allowed_of = {
            "stage": "stages",
            "target": "targets",
            "basis": "bases",
            "allocation": "allocations",
        }
        for kind, spec in EFFECT_SPECS.items():
            base = effect(kind)
            assert unsupported_settings(base) == [], (kind, unsupported_settings(base))
            for name, options in values.items():
                for value in options:
                    rule = replace(base, **{name: value})
                    allowed = value in getattr(spec, allowed_of[name])
                    with self.subTest(kind=kind, setting=name, value=value):
                        assert (unsupported_settings(rule) == []) is allowed

    def test_an_ignored_limit_makes_the_revision_unsupported(self) -> None:
        """A gift with a cap is not silently uncapped."""
        promo = revision(1, effect("gift", params={"quantity": 1}, cap=Decimal(5)))

        result = evaluate(inputs(revisions=(promo,)))

        assert DecisionStatus.UNSUPPORTED in {d.status for d in result.decisions}

    def test_an_application_limit_only_where_the_allocation_counts(self) -> None:
        """A fixed amount once has no application to limit."""
        rule = effect(
            "fixed_amount",
            allocation="once",
            params={"amount": "10"},
            max_applications=1,
        )

        assert unsupported_settings(rule)


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


class SubscriptionConsistencyTests(SimpleTestCase):
    """The schedule agrees with the discount the cart applied."""

    def test_a_capped_first_delivery_matches_the_merchandise(self) -> None:
        """20% capped at R$ 5: R$ 95 now, recurring 10% capped at R$ 5 too."""
        plan = revision(
            1,
            effect(
                "subscription",
                params={
                    "interval_days": 30,
                    "first_delivery_rate": "20",
                    "recurring_rate": "10",
                    "minimum_deliveries": 2,
                },
                cap=Decimal(5),
            ),
        )
        result = evaluate(
            inputs(
                revisions=(plan,),
                context=context(subscription=True),
                policy=policy(allow_conditions=frozenset({"subscription"})),
            ),
        )

        assert result.merchandise_total == Decimal("95.00")
        assert [p.amount for p in result.payment_schedule] == [
            Decimal("95.00"),
            Decimal("95.00"),
        ]
