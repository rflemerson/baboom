"""SYNTHETIC: shipping is quoted for the value of each checkout group."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain.engine import evaluate
from pricing.domain.types import CartLine, CheckoutGroup, ShippingFact
from pricing.tests.domain.builders import context, inputs, offer, price

HUNDRED, TWO_HUNDRED = Decimal(100), Decimal(200)


def _two_groups(*, quotes: tuple[ShippingFact, ...], **kwargs: object) -> object:
    """Offer 1 (R$ 100) in group a, offer 2 (R$ 200) in group b."""
    return inputs(
        context=context(
            CartLine(1),
            CartLine(2),
            groups=(
                CheckoutGroup("a", frozenset({1})),
                CheckoutGroup("b", frozenset({2})),
            ),
        ),
        offers=(offer(1), offer(2)),
        prices=(price(1, "100.00"), price(2, "200.00")),
        shipping=quotes,
        **kwargs,
    )


class GroupShippingTests(SimpleTestCase):
    """A group's quote holds for that group's lines, not for the whole cart."""

    def test_each_group_is_compared_with_its_own_value(self) -> None:
        """R$ 5 for the R$ 100 group and R$ 8 for the R$ 200 one: R$ 13."""
        result = evaluate(
            _two_groups(
                quotes=(
                    ShippingFact("a", Decimal(5), "BRL", order_value=HUNDRED),
                    ShippingFact("b", Decimal(8), "BRL", order_value=TWO_HUNDRED),
                ),
            ),
        )

        assert result.shipping_total == Decimal("13.00")

    def test_a_quote_for_the_whole_cart_does_not_hold_for_a_group(self) -> None:
        """Quoted for R$ 300, the cart's value, neither group's value matches."""
        result = evaluate(
            _two_groups(
                quotes=(
                    ShippingFact("a", Decimal(5), "BRL", order_value=Decimal(300)),
                    ShippingFact("b", Decimal(8), "BRL", order_value=Decimal(300)),
                ),
            ),
        )

        assert result.shipping_total is None
