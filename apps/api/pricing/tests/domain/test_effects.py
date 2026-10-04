"""The branches of each effect: allocation forms, shipping forms, rewards."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain.engine import evaluate
from pricing.domain.money import allocate, round_money
from pricing.domain.types import (
    CartLine,
    DecisionStatus,
    RewardTermsFact,
    ShippingFact,
)
from pricing.tests.domain.builders import context, effect, inputs, policy, revision

SHIPPING = (ShippingFact("all", Decimal("20.00"), "BRL"),)


def _total(promo: object, **kwargs: object) -> object:
    return evaluate(inputs(revisions=(promo,), **kwargs))


class FixedAmountTests(SimpleTestCase):
    """Per unit, per line and once."""

    def test_per_unit_respects_max_applications(self) -> None:
        """R$ 5 per unit on 3 units, at most 2: R$ 10."""
        promo = revision(
            1,
            effect(
                "fixed_amount",
                allocation="per_unit",
                params={"amount": "5"},
                max_applications=2,
            ),
        )

        result = _total(promo, context=context(CartLine(1, 3)))

        assert result.merchandise_total == Decimal("290.00")

    def test_per_line(self) -> None:
        """R$ 5 per line on one line."""
        promo = revision(
            1, effect("fixed_amount", allocation="per_line", params={"amount": "5"})
        )

        assert _total(promo).merchandise_total == Decimal("95.00")


class TierTests(SimpleTestCase):
    """Tiers by amount per unit, and none reached."""

    def test_amount_per_unit_tier(self) -> None:
        """R$ 2 off each of 2 units."""
        tiers = {"tiers": [{"min_quantity": 2, "amount_off_per_unit": "2"}]}
        promo = revision(1, effect("tiered", stage="catalog", params=tiers))

        result = _total(promo, context=context(CartLine(1, 2)))

        assert result.merchandise_total == Decimal("196.00")

    def test_no_tier_reached(self) -> None:
        """One unit reaches no tier."""
        tiers = {"tiers": [{"min_quantity": 2, "rate": "5"}]}
        promo = revision(1, effect("tiered", stage="catalog", params=tiers))

        assert _total(promo).merchandise_total == Decimal("100.00")


class MultibuyTests(SimpleTestCase):
    """Repeat, the most expensive free, and limits."""

    def test_no_repeat_gives_one_group(self) -> None:
        """Six units, buy 3 pay 2, once: one unit free."""
        promo = revision(
            1,
            effect(
                "multibuy",
                stage="catalog",
                params={"buy": 3, "pay": 2, "repeat": False},
            ),
        )

        result = _total(promo, context=context(CartLine(1, 6)))

        assert result.merchandise_total == Decimal("500.00")

    def test_most_expensive_free_and_max_groups(self) -> None:
        """Groups capped by max applications."""
        promo = revision(
            1,
            effect(
                "multibuy",
                stage="catalog",
                params={"buy": 2, "pay": 1, "free_unit": "most_expensive"},
                max_applications=1,
            ),
        )

        result = _total(promo, context=context(CartLine(1, 4)))

        assert result.merchandise_total == Decimal("300.00")


class ShippingTests(SimpleTestCase):
    """Rate, amount and cap on known shipping."""

    def _shipping(self, params: dict, cap: Decimal | None = None) -> object:
        promo = revision(
            1,
            effect(
                "shipping_discount",
                stage="shipping",
                target="shipping",
                basis="component",
                params=params,
                cap=cap,
            ),
        )
        return _total(promo, shipping=SHIPPING)

    def test_rate_amount_and_cap(self) -> None:
        """50% of R$ 20, R$ 5 off, or free capped at R$ 15."""
        assert self._shipping({"rate": "50"}).shipping_total == Decimal("10.00")
        assert self._shipping({"amount": "5"}).shipping_total == Decimal("15.00")
        assert self._shipping(
            {"free": True}, cap=Decimal(15)
        ).shipping_total == Decimal(
            "5.00",
        )


class SubscriptionTests(SimpleTestCase):
    """A subscription applies only when chosen."""

    def test_not_chosen_and_unknown(self) -> None:
        """Declined: ineligible; not stated: unknown."""
        plan = revision(
            1,
            effect(
                "subscription",
                stage="catalog",
                params={"interval_days": 30, "recurring_rate": "10"},
            ),
        )
        allowed = policy(allow_conditions=frozenset({"subscription"}))

        declined = _total(plan, policy=allowed, context=context(subscription=False))
        unknown = _total(plan, policy=allowed)

        statuses = {d.status for d in declined.decisions if d.subject == "revision 1"}
        assert DecisionStatus.INELIGIBLE in statuses
        assert DecisionStatus.UNKNOWN in {
            d.status for d in unknown.decisions if d.subject == "revision 1"
        }


class RewardTests(SimpleTestCase):
    """Cashback minimums, bases and points by count."""

    rewards = policy(allow_rewards=True)

    def _cashback(self, terms: RewardTermsFact, **kwargs: object) -> object:
        promo = revision(1, effect("cashback", stage="reward", reward=terms))
        return _total(promo, policy=self.rewards, **kwargs)

    def test_below_minimum_and_unknown_rate(self) -> None:
        """No cashback below its minimum; none computed without a rate."""
        below = self._cashback(
            RewardTermsFact(credited_as="money", rate=Decimal(5), minimum=Decimal(200)),
        )
        no_rate = self._cashback(RewardTermsFact(credited_as="money"))

        assert below.deferred_rewards == ()
        assert no_rate.deferred_rewards == ()

    def test_bases(self) -> None:
        """Before discounts, the order total, and shipping when it is known."""
        before = self._cashback(
            RewardTermsFact(
                credited_as="money",
                rate=Decimal(10),
                eligible_basis="items_before_discounts",
            ),
        )
        order = self._cashback(
            RewardTermsFact(
                credited_as="money", rate=Decimal(10), eligible_basis="order_total"
            ),
        )
        with_shipping = self._cashback(
            RewardTermsFact(
                credited_as="money", rate=Decimal(10), includes_shipping=True
            ),
            shipping=SHIPPING,
        )
        shipping_unknown = self._cashback(
            RewardTermsFact(
                credited_as="money", rate=Decimal(10), includes_shipping=True
            ),
        )

        assert before.deferred_rewards[0].amount == Decimal("10.00")
        assert order.deferred_rewards[0].amount == Decimal("10.00")
        assert with_shipping.deferred_rewards[0].amount == Decimal("12.00")
        assert shipping_unknown.deferred_rewards == ()

    def test_a_transaction_cap(self) -> None:
        """A per-transaction cap needs no assumption."""
        capped = self._cashback(
            RewardTermsFact(
                credited_as="money",
                rate=Decimal(10),
                cap=Decimal(3),
                cap_period="transaction",
            ),
        )

        assert capped.deferred_rewards[0].amount == Decimal("3.00")
        assert capped.assumptions == ()

    def test_fixed_points(self) -> None:
        """A fixed number of points."""
        promo = revision(
            1,
            effect(
                "points",
                stage="reward",
                params={"points": 50},
                reward=RewardTermsFact(credited_as="points", program_id=9),
            ),
        )

        result = _total(promo, policy=self.rewards)

        assert result.deferred_rewards[0].amount == Decimal(50)
        assert result.deferred_rewards[0].unit == "9"


class MoneyTests(SimpleTestCase):
    """Rounding and allocation edges."""

    def test_allocation_edges(self) -> None:
        """No weights, zero weights, and half-up rounding."""
        assert allocate(Decimal(1), [], 2) == []
        assert allocate(Decimal(1), [Decimal(0), Decimal(0)], 2) == [
            Decimal("1.00"),
            Decimal(0),
        ]
        assert round_money(Decimal("0.125"), 2) == Decimal("0.13")


class PolicyTests(SimpleTestCase):
    """Scenarios and statuses the matrix does not reach."""

    def test_scenario_and_status_refusals(self) -> None:
        """Unknown scenario, payment without choice, drafts, informative, codes."""
        unknown_scenario = evaluate(inputs(policy=policy("someday")))
        payment_unchosen = evaluate(inputs(policy=policy("payment")))
        suspended = _total(
            revision(1, effect("percentage", params={"rate": "5"}), status="suspended"),
        )
        informative = _total(
            revision(
                1, effect("percentage", params={"rate": "5"}), status="informative"
            ),
        )
        personal = _total(
            revision(
                1,
                effect("percentage", params={"rate": "5"}),
                codes=(("personal_code", "MINE"),),
            ),
            policy=policy(allow_codes=True),
        )
        unsupported = _total(revision(1, effect("lottery")))

        assert unknown_scenario.merchandise_total is None
        assert payment_unchosen.merchandise_total is None
        for result, status in (
            (suspended, DecisionStatus.INELIGIBLE),
            (informative, DecisionStatus.INFORMATIVE),
            (personal, DecisionStatus.INELIGIBLE),
            (unsupported, DecisionStatus.UNSUPPORTED),
        ):
            assert status in {d.status for d in result.decisions}

    def test_not_started_and_rewards_only(self) -> None:
        """A future revision waits; a rewards-only revision needs rewards."""
        future = _total(
            revision(
                1,
                effect("percentage", params={"rate": "5"}),
                starts_at=context().now.replace(year=2027),
            ),
        )
        rewards_only = _total(
            revision(
                1,
                effect(
                    "cashback",
                    stage="reward",
                    reward=RewardTermsFact(credited_as="money", rate=Decimal(5)),
                ),
            ),
        )

        assert future.merchandise_total == Decimal("100.00")
        assert any("rewards" in d.reason for d in rewards_only.decisions)

    def test_an_offer_not_given(self) -> None:
        """A line naming no known offer has no price."""
        result = evaluate(inputs(context=replace(context(), lines=(CartLine(99),))))

        assert result.merchandise_total is None
