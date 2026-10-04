"""SYNTHETIC: the best scenario searches how to pay, never assuming a method."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain.engine import evaluate
from pricing.domain.types import PaymentChoice
from pricing.tests.domain.builders import (
    context,
    effect,
    inputs,
    policy,
    price,
    revision,
)

PIX_ONLY = {"root": {"kind": "payment_method", "codes": ["pix"]}}
CARD_ONLY = {"root": {"kind": "payment_method", "codes": ["credit_card"]}}
BEST = policy("best", allow_conditions=frozenset({"payment_method"}))


def _promotion(conditions: dict) -> object:
    return revision(
        7,
        effect("percentage", stage="payment", params={"rate": "20"}),
        conditions=conditions,
    )


def _pix(amount: str) -> object:
    return price(
        1,
        amount,
        payment_scope="method",
        payment_method="pix",
        installment_count=1,
        included_adjustments=("payment_discount",),
    )


def _card(amount: str) -> object:
    return price(
        1,
        amount,
        payment_scope="method",
        payment_method="credit_card",
        installment_count=1,
    )


class PaymentSearchTests(SimpleTestCase):
    """Bases times ways to pay, each with the promotions that fit it."""

    def test_a_pix_promotion_applies_on_the_price_that_has_no_discount(self) -> None:
        """R$ 100 for any method with 20% off in Pix beats the R$ 90 Pix price."""
        result = evaluate(
            inputs(
                prices=(price(1, "100.00", payment_scope="any"), _pix("90.00")),
                revisions=(_promotion(PIX_ONLY),),
                policy=BEST,
            ),
        )

        assert result.merchandise_total == Decimal("80.00")
        assert result.payment == PaymentChoice("pix", 1)
        assert result.applied_revisions == (7,)
        assert [p.amount for p in result.payment_schedule] == [Decimal("80.00")]

    def test_a_pix_promotion_never_applies_to_a_card_payment(self) -> None:
        """Paying by card, the Pix promotion stays out."""
        result = evaluate(
            inputs(
                prices=(_card("100.00"),),
                revisions=(_promotion(PIX_ONLY),),
                policy=policy(
                    "payment", allow_conditions=frozenset({"payment_method"})
                ),
                context=context(payment=PaymentChoice("credit_card", 1)),
            ),
        )

        assert result.merchandise_total == Decimal("100.00")
        assert result.payment == PaymentChoice("credit_card", 1)
        assert result.applied_revisions == ()

    def test_a_card_promotion_does_not_reach_an_any_price_in_the_best_scenario(
        self,
    ) -> None:
        """Only methods paid at once are searched: the card is not one."""
        result = evaluate(
            inputs(
                prices=(price(1, "100.00", payment_scope="any"),),
                revisions=(_promotion(CARD_ONLY),),
                policy=BEST,
            ),
        )

        assert result.merchandise_total == Decimal("100.00")
        assert result.applied_revisions == ()

    def test_a_card_promotion_never_reduces_a_pix_price(self) -> None:
        """A price of Pix fixes Pix: the card promotion is another method."""
        result = evaluate(
            inputs(
                prices=(_pix("90.00"),),
                revisions=(_promotion(CARD_ONLY),),
                policy=BEST,
            ),
        )

        assert result.merchandise_total == Decimal("90.00")
        assert result.applied_revisions == ()

    def test_a_method_condition_stays_unknown_for_an_unstated_payment(self) -> None:
        """A price that states no payment cannot take a Pix promotion."""
        result = evaluate(
            inputs(
                prices=(price(1, "100.00"),),
                revisions=(_promotion(PIX_ONLY),),
                policy=BEST,
            ),
        )

        assert result.merchandise_total == Decimal("100.00")
        assert result.payment is None
        assert result.applied_revisions == ()

    def test_without_cash_methods_an_any_price_takes_no_method_promotion(self) -> None:
        """The policy names which methods are paid at once."""
        result = evaluate(
            inputs(
                prices=(price(1, "100.00", payment_scope="any"),),
                revisions=(_promotion(PIX_ONLY),),
                policy=policy(
                    "best",
                    allow_conditions=frozenset({"payment_method"}),
                    cash_methods=frozenset(),
                ),
            ),
        )

        assert result.merchandise_total == Decimal("100.00")

    def test_the_chosen_installments_travel_to_the_schedule(self) -> None:
        """A payment in three installments is scheduled in three."""
        result = evaluate(
            inputs(
                prices=(
                    price(
                        1,
                        "120.00",
                        payment_scope="method",
                        payment_method="credit_card",
                        installment_count=3,
                    ),
                ),
                policy=policy("payment"),
                context=context(payment=PaymentChoice("credit_card", 3)),
            ),
        )

        assert result.payment == PaymentChoice("credit_card", 3)
        assert [p.amount for p in result.payment_schedule] == [Decimal("40.00")] * 3
