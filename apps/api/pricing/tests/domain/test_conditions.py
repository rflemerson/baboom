"""Every condition leaf, and the three-valued logic that combines them."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain.conditions import Amounts, ConditionInput, evaluate
from pricing.domain.types import Claim, Destination, PaymentChoice, Tri
from pricing.tests.domain.builders import context, offer, revision

AMOUNTS = Amounts(
    before_discounts=Decimal(210),
    after_item_discounts=Decimal(189),
    after_order_discounts=Decimal(189),
    shipping=Decimal(12),
    quantity=3,
)
NO_SHIPPING = Amounts(Decimal(210), Decimal(189), Decimal(189), None, 3)


def _eval(leaf: dict | None, **context_args: object) -> Tri:
    data = ConditionInput(
        context=context(**context_args),
        revision=revision(1, codes=(("public_code", "CODE"),)),
        offers=(offer(),),
        qualifying=AMOUNTS,
        order=AMOUNTS,
    )
    return evaluate({"root": leaf}, data).value


def _min(amount: str, basis: str = "before_discounts", **extra: object) -> dict:
    return {
        "kind": "min_amount",
        "amount": amount,
        "currency": "BRL",
        "basis": basis,
        "scope": "order",
        **extra,
    }


class LogicTests(SimpleTestCase):
    """all, any and not over true, false and unknown."""

    def test_no_root_is_unconditional(self) -> None:
        """An empty tree holds."""
        assert _eval(None) is Tri.TRUE

    def test_all_any_not(self) -> None:
        """False wins in all, true wins in any, unknown stays unknown under not."""
        true, false = _min("1"), _min("1000")
        unknown = {"kind": "payment_method", "codes": ["pix"]}

        assert _eval({"all": [true, unknown]}) is Tri.UNKNOWN
        assert _eval({"all": [false, unknown]}) is Tri.FALSE
        assert _eval({"any": [true, unknown]}) is Tri.TRUE
        assert _eval({"any": [false, unknown]}) is Tri.UNKNOWN
        assert _eval({"any": [false, false]}) is Tri.FALSE
        assert _eval({"not": true}) is Tri.FALSE
        assert _eval({"not": unknown}) is Tri.UNKNOWN

    def test_malformed_and_unsupported_nodes_are_unknown(self) -> None:
        """Nothing unreadable becomes true."""
        assert _eval({"kind": "lottery"}) is Tri.UNKNOWN
        assert _eval({"all": ["text"]}) is Tri.UNKNOWN


class AmountTests(SimpleTestCase):
    """Minimums are measured on their declared basis."""

    def test_basis_decides(self) -> None:
        """R$ 200 holds before discounts (R$ 210), not after (R$ 189)."""
        assert _eval(_min("200")) is Tri.TRUE
        assert _eval(_min("200", "after_item_discounts")) is Tri.FALSE

    def test_shipping_included_when_stated(self) -> None:
        """R$ 189 + R$ 12 shipping reaches R$ 200."""
        assert _eval(_min("200", "after_item_discounts", includes_shipping=True)) is (
            Tri.TRUE
        )

    def test_unknown_shipping_or_currency_is_unknown(self) -> None:
        """Without the shipping or in another currency, the minimum cannot be read."""
        data = ConditionInput(
            context=context(),
            revision=revision(1),
            offers=(offer(),),
            qualifying=NO_SHIPPING,
            order=NO_SHIPPING,
        )
        leaf = _min("200", includes_shipping=True)
        assert evaluate({"root": leaf}, data).value is Tri.UNKNOWN
        assert _eval({**_min("1"), "currency": "USD"}) is Tri.UNKNOWN
        assert _eval({**_min("1"), "basis": "someday"}) is Tri.UNKNOWN

    def test_min_quantity(self) -> None:
        """Three units reach three, not four."""
        assert (
            _eval({"kind": "min_quantity", "quantity": 3, "scope": "order"}) is Tri.TRUE
        )
        assert _eval({"kind": "min_quantity", "quantity": 4, "scope": "order"}) is (
            Tri.FALSE
        )


class WhoAndWhereTests(SimpleTestCase):
    """Channel, market, seller and destination."""

    def test_channel_market_seller(self) -> None:
        """The default offer is channel 10, market 1, seller 100."""
        assert _eval({"kind": "channel", "channel_ids": [10]}) is Tri.TRUE
        assert _eval({"kind": "market", "market_ids": [2]}) is Tri.FALSE
        assert _eval({"kind": "seller", "seller_account_ids": [100]}) is Tri.TRUE

    def test_unknown_seller_is_unknown(self) -> None:
        """An offer whose seller is not known cannot satisfy a seller condition."""
        data = ConditionInput(
            context=context(),
            revision=revision(1),
            offers=(offer(seller=None),),
            qualifying=AMOUNTS,
            order=AMOUNTS,
        )
        leaf = {"kind": "seller", "seller_account_ids": [100]}
        assert evaluate({"root": leaf}, data).value is Tri.UNKNOWN

    def test_destination(self) -> None:
        """Country, subdivision and postal prefix, each unknown when not given."""
        leaf = {
            "kind": "destination",
            "country": "BR",
            "subdivisions": ["SP"],
            "postal_prefixes": ["01"],
        }
        sao_paulo = Destination("BR", "SP", postal_code="01310-100")

        assert _eval(leaf) is Tri.UNKNOWN
        assert _eval(leaf, destination=sao_paulo) is Tri.TRUE
        assert _eval(leaf, destination=Destination("MX")) is Tri.FALSE
        assert _eval(leaf, destination=Destination("BR", "RJ")) is Tri.FALSE
        assert _eval(leaf, destination=Destination("BR")) is Tri.UNKNOWN
        outside = Destination("BR", "SP", postal_code="20000-000")
        assert _eval(leaf, destination=outside) is Tri.FALSE


class BuyerTests(SimpleTestCase):
    """Payment, programmes, subscriptions, claims, calendar and codes."""

    def test_payment_method(self) -> None:
        """The method and the most installments the terms allow."""
        leaf = {
            "kind": "payment_method",
            "codes": ["credit_card"],
            "max_installments": 3,
        }

        assert _eval(leaf) is Tri.UNKNOWN
        assert _eval(leaf, payment=PaymentChoice("credit_card", 3)) is Tri.TRUE
        assert _eval(leaf, payment=PaymentChoice("credit_card", 6)) is Tri.FALSE
        assert _eval(leaf, payment=PaymentChoice("pix")) is Tri.FALSE

    def test_program_member(self) -> None:
        """A programme in the context, or a claim, or unknown."""
        leaf = {"kind": "program_member", "program_id": 7}

        assert _eval(leaf) is Tri.UNKNOWN
        assert _eval(leaf, programs=frozenset({7})) is Tri.TRUE
        claim = Claim("program_member", "program", 7, value=False)
        assert _eval(leaf, claims=(claim,)) is Tri.FALSE

    def test_subscription(self) -> None:
        """Chosen or not, or unknown."""
        leaf = {"kind": "subscription", "required": True}

        assert _eval(leaf) is Tri.UNKNOWN
        assert _eval(leaf, subscription=True) is Tri.TRUE
        assert _eval(leaf, subscription=False) is Tri.FALSE

    def test_calendar(self) -> None:
        """Weekdays and local hours, in the revision's time zone."""
        friday_noon = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)  # 12:00 in São Paulo
        weekdays = {"kind": "calendar", "weekdays": [4]}
        morning = {"kind": "calendar", "start_time": "06:00", "end_time": "11:00"}
        evening = {"kind": "calendar", "start_time": "13:00"}

        assert _eval(weekdays, now=friday_noon) is Tri.TRUE
        assert (
            _eval({"kind": "calendar", "weekdays": [0]}, now=friday_noon) is Tri.FALSE
        )
        assert _eval(morning, now=friday_noon) is Tri.FALSE
        assert _eval(evening, now=friday_noon) is Tri.FALSE
        assert _eval({"kind": "calendar"}, now=friday_noon) is Tri.TRUE

    def test_code_required(self) -> None:
        """The revision's code must be entered."""
        assert _eval({"kind": "code_required"}) is Tri.FALSE
        assert _eval({"kind": "code_required"}, codes=frozenset({"CODE"})) is Tri.TRUE
