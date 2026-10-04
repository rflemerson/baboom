"""The acceptance matrix of the pricing engine, offline and synthetic."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain.engine import evaluate, fingerprint
from pricing.domain.money import allocate
from pricing.domain.types import (
    CartLine,
    CheckoutGroup,
    Claim,
    CompatibilityFact,
    DecisionStatus,
    Destination,
    FeeFact,
    OptimizationStatus,
    PaymentChoice,
    RewardTermsFact,
    ScopeRule,
    ShippingFact,
)
from pricing.tests.domain.builders import (
    NOW,
    context,
    effect,
    inputs,
    offer,
    policy,
    price,
    revision,
)

PIX_DISCOUNT = ("payment_discount",)


def _statuses(result: object) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for decision in result.decisions:
        found.setdefault(decision.subject, set()).add(decision.status)
    return found


class BasePriceTests(SimpleTestCase):
    """The base price is chosen by scenario, never invented."""

    def test_reference_price_is_never_payable(self) -> None:
        """A "de" price alone prices nothing."""
        result = evaluate(inputs(prices=(price(1, "149.90", role="reference"),)))

        assert result.merchandise_total is None
        assert result.missing_context

    def test_cash_scenario_takes_the_pix_price(self) -> None:
        """R$ 114 by Pix beats R$ 120 unstated, in the cash scenario."""
        result = evaluate(
            inputs(
                prices=(
                    price(1, "120.00"),
                    price(
                        1,
                        "114.00",
                        payment_scope="method",
                        payment_method="pix",
                        installment_count=1,
                        included_adjustments=PIX_DISCOUNT,
                    ),
                ),
                policy=policy("cash"),
            ),
        )

        assert result.merchandise_total == Decimal("114.00")
        assert result.selected_prices[0].payment_method == "pix"

    def test_an_unknown_payment_method_is_not_any(self) -> None:
        """A wallet price the adapter could not name never wins the cash scenario."""
        result = evaluate(
            inputs(
                prices=(
                    price(1, "120.00"),
                    price(1, "90.00", payment_scope="method", payment_method=""),
                ),
                policy=policy("cash"),
            ),
        )

        assert result.merchandise_total == Decimal("120.00")

    def test_installments_are_compared_by_total_not_installment(self) -> None:
        """3 x R$ 40 is R$ 120, scheduled in three payments."""
        result = evaluate(
            inputs(
                prices=(
                    price(
                        1,
                        "120.00",
                        payment_scope="method",
                        payment_method="credit_card",
                        installment_count=3,
                        installment_amount=Decimal("40.00"),
                        interest="no",
                    ),
                ),
                policy=policy("payment"),
                context=context(payment=PaymentChoice("credit_card", 3)),
            ),
        )

        assert result.total_payable is None  # shipping unknown
        assert result.merchandise_total == Decimal("120.00")
        assert [p.amount for p in result.payment_schedule] == [Decimal("40.00")] * 3

    def test_a_stale_price_is_not_used(self) -> None:
        """Past its freshness, a price is reported stale."""
        stale = price(1, "80.00", fresh_until=NOW - timedelta(hours=1))
        result = evaluate(inputs(prices=(stale, price(1, "100.00"))))

        assert result.merchandise_total == Decimal("100.00")
        assert DecisionStatus.STALE in _statuses(result)[f"price {stale.id}"]

    def test_an_unpurchasable_offer_has_no_price(self) -> None:
        """Out of stock or delisted never wins."""
        result = evaluate(inputs(offers=(offer(purchasable=False),)))

        assert result.merchandise_total is None
        assert DecisionStatus.INELIGIBLE in _statuses(result)["offer 1"]

    def test_a_refused_source_is_access_unavailable_not_zero(self) -> None:
        """A 403 or 429 is not a free product."""
        result = evaluate(inputs(offers=(offer(access_available=False),)))

        assert result.merchandise_total is None
        assert DecisionStatus.ACCESS_UNAVAILABLE in _statuses(result)["offer 1"]


class DiscountTests(SimpleTestCase):
    """Effects, bases, caps and allocation."""

    def test_payment_discount_already_in_the_price_is_not_applied_again(self) -> None:
        """A 5% Pix promotion on a Pix price that includes it is a conflict."""
        pix_promo = revision(
            7, effect("percentage", stage="payment", params={"rate": "5"})
        )
        result = evaluate(
            inputs(
                prices=(
                    price(
                        1,
                        "114.00",
                        payment_scope="method",
                        payment_method="pix",
                        installment_count=1,
                        included_adjustments=PIX_DISCOUNT,
                    ),
                ),
                revisions=(pix_promo,),
                policy=policy("cash"),
            ),
        )

        assert result.merchandise_total == Decimal("114.00")
        assert DecisionStatus.CONFLICT in _statuses(result)["revision 7"]

    def test_bases_change_the_result_order_alone_does_not(self) -> None:
        """10% and 5% on R$ 100: both on the initial price R$ 85, chained R$ 85.50."""
        on_initial = revision(
            1,
            effect("percentage", 1, basis="initial", params={"rate": "10"}),
            effect("percentage", 2, basis="initial", params={"rate": "5"}),
            ordering=((1, 2),),
        )
        chained = replace(
            on_initial,
            effects=(
                effect("percentage", 1, basis="current", params={"rate": "10"}),
                effect("percentage", 2, basis="current", params={"rate": "5"}),
            ),
        )

        assert evaluate(inputs(revisions=(on_initial,))).merchandise_total == Decimal(
            "85.00",
        )
        assert evaluate(inputs(revisions=(chained,))).merchandise_total == Decimal(
            "85.50",
        )

    def test_a_discount_never_exceeds_its_basis(self) -> None:
        """R$ 150 off a R$ 100 item leaves zero, not minus fifty."""
        big = revision(1, effect("fixed_amount", params={"amount": "150"}))

        result = evaluate(inputs(revisions=(big,)))

        assert result.merchandise_total == Decimal("0.00")
        assert result.adjustments[0].amount == Decimal("100.00")

    def test_a_cap_limits_the_discount(self) -> None:
        """20% capped at R$ 15."""
        capped = revision(
            1, effect("percentage", params={"rate": "20"}, cap=Decimal(15))
        )

        assert evaluate(inputs(revisions=(capped,))).merchandise_total == Decimal(
            "85.00"
        )

    def test_allocation_of_a_cent_is_exact_and_stable(self) -> None:
        """R$ 0.01 over three equal lines goes to the first."""
        assert allocate(Decimal("0.01"), [Decimal(1)] * 3, 2) == [
            Decimal("0.01"),
            Decimal("0.00"),
            Decimal("0.00"),
        ]
        shares = allocate(Decimal("10.00"), [Decimal(1)] * 3, 2)
        assert sum(shares) == Decimal("10.00")

    def test_buy_three_pay_two_needs_three_units(self) -> None:
        """One unit gets no multibuy; three get the cheapest free."""
        promo = revision(
            1,
            effect(
                "multibuy", stage="catalog", target="item", params={"buy": 3, "pay": 2}
            ),
        )
        one = evaluate(inputs(revisions=(promo,)))
        three = evaluate(
            inputs(revisions=(promo,), context=context(CartLine(1, 3))),
        )

        assert one.merchandise_total == Decimal("100.00")
        assert three.merchandise_total == Decimal("200.00")

    def test_quantity_tiers_take_the_highest_reached(self) -> None:
        """5% from 2 units, 10% from 4."""
        tiers = {
            "tiers": [
                {"min_quantity": 2, "rate": "5"},
                {"min_quantity": 4, "rate": "10"},
            ],
        }
        promo = revision(1, effect("tiered", stage="catalog", params=tiers))
        result = evaluate(inputs(revisions=(promo,), context=context(CartLine(1, 4))))

        assert result.merchandise_total == Decimal("360.00")

    def test_fixed_price(self) -> None:
        """The target sells at R$ 79.90."""
        promo = revision(
            1, effect("fixed_price", stage="catalog", params={"price": "79.90"})
        )

        assert evaluate(inputs(revisions=(promo,))).merchandise_total == Decimal(
            "79.90"
        )

    def test_a_seller_coupon_reaches_only_that_seller(self) -> None:
        """Lines of another seller keep their price."""
        promo = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            scopes=(ScopeRule("target", "include", "seller_account", 100),),
        )
        result = evaluate(
            inputs(
                offers=(offer(1, seller=100), offer(2, seller=200)),
                prices=(price(1, "100.00"), price(2, "100.00")),
                revisions=(promo,),
                context=context(CartLine(1), CartLine(2)),
            ),
        )

        assert result.merchandise_total == Decimal("190.00")
        assert result.adjustments[0].allocations == ((1, Decimal("10.00")),)

    def test_an_exclusion_wins_over_an_inclusion(self) -> None:
        """Market included, this offer excluded."""
        promo = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            scopes=(
                ScopeRule("target", "include", "market", 1),
                ScopeRule("target", "exclude", "offer", 1),
            ),
        )

        result = evaluate(inputs(revisions=(promo,)))

        assert result.merchandise_total == Decimal("100.00")

    def test_a_gift_is_never_money(self) -> None:
        """A shaker comes along; the price does not move."""
        promo = revision(
            1, effect("gift", params={"description": "shaker", "quantity": 1})
        )
        result = evaluate(inputs(revisions=(promo,)))

        assert result.merchandise_total == Decimal("100.00")
        assert result.gifts[0].description == "shaker"


class CombinationTests(SimpleTestCase):
    """Compatibility decides what combines; the best allowed combination wins."""

    def test_incompatible_coupons_never_add_up(self) -> None:
        """Without evidence they combine, the better one alone is applied."""
        ten = revision(1, effect("percentage", params={"rate": "10"}))
        fifteen = revision(2, effect("percentage", params={"rate": "15"}))

        result = evaluate(inputs(revisions=(ten, fifteen)))

        assert result.merchandise_total == Decimal("85.00")
        assert result.applied_revisions == (2,)

    def test_explicitly_compatible_promotions_combine(self) -> None:
        """Evidence that they stack lets both apply."""
        ten = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            compatibility=(CompatibilityFact("promotion", "2", "allowed"),),
        )
        five = revision(2, effect("percentage", basis="current", params={"rate": "5"}))

        result = evaluate(inputs(revisions=(ten, five)))

        assert result.merchandise_total == Decimal("85.50")

    def test_a_forbidding_side_wins_over_an_allowing_one(self) -> None:
        """One side cannot authorize itself to combine."""
        ten = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            compatibility=(CompatibilityFact("promotion", "2", "allowed"),),
        )
        five = revision(
            2,
            effect("percentage", params={"rate": "5"}),
            compatibility=(CompatibilityFact("promotion", "1", "forbidden"),),
        )

        assert evaluate(inputs(revisions=(ten, five))).applied_revisions == (1,)

    def test_a_store_imposed_choice_is_an_assumption(self) -> None:
        """When the store picks, the engine does not pick the better one silently."""
        ten = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            compatibility=(
                CompatibilityFact("promotion", "2", "forbidden", "store_imposed"),
            ),
        )
        twenty = revision(2, effect("percentage", params={"rate": "20"}))

        result = evaluate(inputs(revisions=(ten, twenty)))

        assert result.applied_revisions == (1,)
        assert result.assumptions

    def test_bounded_search_says_so(self) -> None:
        """A truncated search never claims the lowest possible price."""
        promos = tuple(
            revision(n, effect("percentage", params={"rate": "1"})) for n in range(1, 6)
        )

        result = evaluate(
            inputs(revisions=promos, policy=policy(max_combinations=3)),
        )

        assert result.optimization_status == OptimizationStatus.BOUNDED


class ConditionTests(SimpleTestCase):
    """Conditions are true, false or unknown, and policies choose which count."""

    def test_an_unknown_first_purchase_is_unknown(self) -> None:
        """No claim: the benefit is not applied, and the reason says why."""
        first = revision(
            1,
            effect("percentage", params={"rate": "20"}),
            conditions={
                "root": {"kind": "new_customer", "issuer": "seller", "issuer_id": 100},
            },
        )
        personal = policy(allow_conditions=frozenset({"new_customer"}))

        unknown = evaluate(inputs(revisions=(first,), policy=personal))
        claimed = evaluate(
            inputs(
                revisions=(first,),
                policy=personal,
                context=context(claims=(Claim("new_customer", "seller", 100),)),
            ),
        )

        assert unknown.merchandise_total == Decimal("100.00")
        assert DecisionStatus.UNKNOWN in _statuses(unknown)["revision 1"]
        assert claimed.merchandise_total == Decimal("80.00")

    def test_the_public_ranking_excludes_first_purchase_terms(self) -> None:
        """The default scenario never counts eligibility claims."""
        first = revision(
            1,
            effect("percentage", params={"rate": "20"}),
            conditions={
                "root": {"kind": "new_customer", "issuer": "seller", "issuer_id": 100},
            },
        )

        result = evaluate(inputs(revisions=(first,)))

        assert DecisionStatus.INELIGIBLE in _statuses(result)["revision 1"]

    def test_a_code_is_needed_when_the_terms_require_it(self) -> None:
        """No code entered, no discount."""
        coupon = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            codes=(("public_code", "BABOOM10"),),
            conditions={"root": {"kind": "code_required"}},
        )
        with_codes = policy(allow_codes=True)

        without = evaluate(inputs(revisions=(coupon,), policy=with_codes))
        entered = evaluate(
            inputs(
                revisions=(coupon,),
                policy=with_codes,
                context=context(codes=frozenset({"BABOOM10"})),
            ),
        )

        assert without.merchandise_total == Decimal("100.00")
        assert entered.merchandise_total == Decimal("90.00")

    def test_an_expired_campaign_no_longer_applies(self) -> None:
        """End is exclusive."""
        ended = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            ends_at=NOW,
        )

        result = evaluate(inputs(revisions=(ended,)))

        assert result.merchandise_total == Decimal("100.00")
        assert DecisionStatus.INELIGIBLE in _statuses(result)["revision 1"]

    def test_terms_in_another_currency_are_unsupported(self) -> None:
        """Amounts of different currencies never add up."""
        dollars = revision(
            1, effect("fixed_amount", params={"amount": "5"}), currency="USD"
        )

        result = evaluate(inputs(revisions=(dollars,)))

        assert DecisionStatus.UNSUPPORTED in _statuses(result)["revision 1"]

    def test_a_minimum_after_the_coupon_can_lose_free_shipping(self) -> None:
        """R$ 210 with 10% off: R$ 189 after the coupon misses a R$ 200 minimum."""
        coupon = revision(
            1,
            effect("percentage", stage="catalog", params={"rate": "10"}),
            compatibility=(CompatibilityFact("promotion", "2", "allowed"),),
        )

        def free_shipping(basis: str) -> object:
            return revision(
                2,
                effect(
                    "shipping_discount",
                    stage="shipping",
                    target="shipping",
                    basis="component",
                    params={"free": True},
                ),
                conditions={
                    "root": {
                        "kind": "min_amount",
                        "amount": "200",
                        "currency": "BRL",
                        "basis": basis,
                        "scope": "order",
                    },
                },
            )

        def run(basis: str) -> object:
            return evaluate(
                inputs(
                    prices=(price(1, "210.00"),),
                    revisions=(coupon, free_shipping(basis)),
                    shipping=(ShippingFact("all", Decimal("12.00"), "BRL"),),
                ),
            )

        after = run("after_item_discounts")
        before = run("before_discounts")

        assert after.total_payable == Decimal("201.00")
        assert before.total_payable == Decimal("189.00")


class TotalsTests(SimpleTestCase):
    """Shipping, fees, rewards and the full example of the research."""

    def test_unknown_shipping_leaves_the_total_unknown(self) -> None:
        """Merchandise is known; the delivered total is not zero shipping."""
        result = evaluate(inputs())

        assert result.merchandise_total == Decimal("100.00")
        assert result.total_payable is None
        assert any("shipping" in item for item in result.missing_context)

    def test_shipping_per_checkout_group(self) -> None:
        """Two sellers, two packages: both are paid, a missing one is unknown."""
        groups = (
            CheckoutGroup("a", frozenset({1})),
            CheckoutGroup("b", frozenset({2})),
        )
        base = inputs(
            offers=(offer(1, seller=100), offer(2, seller=200)),
            prices=(price(1, "100.00"), price(2, "50.00")),
            context=context(CartLine(1), CartLine(2), groups=groups),
        )

        both = evaluate(
            replace(
                base,
                shipping=(
                    ShippingFact("a", Decimal("10.00"), "BRL"),
                    ShippingFact("b", Decimal("8.00"), "BRL"),
                ),
            ),
        )
        one = evaluate(
            replace(base, shipping=(ShippingFact("a", Decimal("10.00"), "BRL"),)),
        )

        assert both.total_payable == Decimal("168.00")
        assert one.total_payable is None

    def test_a_tax_already_in_the_price_is_not_added_again(self) -> None:
        """Included taxes are ignored; an unknown fee leaves the total unknown."""
        shipping = (ShippingFact("all", Decimal(0), "BRL"),)
        included = evaluate(
            inputs(
                shipping=shipping,
                fees=(
                    FeeFact(
                        "all", "vat", Decimal("17.00"), "BRL", included_in_price=True
                    ),
                ),
            ),
        )
        unknown = evaluate(
            inputs(
                shipping=shipping, fees=(FeeFact("all", "import_tax", None, "BRL"),)
            ),
        )

        assert included.total_payable == Decimal("100.00")
        assert unknown.total_payable is None

    def test_the_full_example_of_the_research(self) -> None:
        """R$ 114 Pix, 10% coupon stacking, R$ 12 shipping, 5% cashback."""
        terms = RewardTermsFact(credited_as="money", rate=Decimal(5))
        coupon = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            compatibility=(CompatibilityFact("promotion", "2", "allowed"),),
        )
        cashback = revision(
            2,
            effect(
                "cashback",
                stage="reward",
                basis="eligible_subtotal",
                allocation="once",
                reward=terms,
            ),
        )
        result = evaluate(
            inputs(
                prices=(
                    price(1, "149.90", role="reference"),
                    price(1, "120.00"),
                    price(
                        1,
                        "114.00",
                        payment_scope="method",
                        payment_method="pix",
                        installment_count=1,
                        included_adjustments=PIX_DISCOUNT,
                    ),
                ),
                revisions=(coupon, cashback),
                shipping=(ShippingFact("all", Decimal("12.00"), "BRL"),),
                policy=policy(
                    "cash",
                    allow_rewards=True,
                    net_cost_counts_money_rewards=True,
                ),
            ),
        )

        assert result.merchandise_total == Decimal("102.60")
        assert result.total_payable == Decimal("114.60")
        assert result.deferred_rewards[0].amount == Decimal("5.13")
        assert result.estimated_net_cost == Decimal("109.47")

    def test_restricted_credit_never_lowers_the_net_cost(self) -> None:
        """Store credit is shown, not subtracted."""
        credit = revision(
            1,
            effect(
                "cashback",
                stage="reward",
                reward=RewardTermsFact(
                    credited_as="restricted_credit", rate=Decimal(10)
                ),
            ),
        )
        result = evaluate(
            inputs(
                revisions=(credit,),
                shipping=(ShippingFact("all", Decimal(0), "BRL"),),
                policy=policy(allow_rewards=True, net_cost_counts_money_rewards=True),
            ),
        )

        assert result.deferred_rewards[0].amount == Decimal("10.00")
        assert result.estimated_net_cost == result.total_payable

    def test_cashback_excludes_shipping_unless_stated(self) -> None:
        """5% of R$ 100, not of R$ 112."""
        cashback = revision(
            1,
            effect(
                "cashback",
                stage="reward",
                reward=RewardTermsFact(credited_as="money", rate=Decimal(5)),
            ),
        )
        result = evaluate(
            inputs(
                revisions=(cashback,),
                shipping=(ShippingFact("all", Decimal("12.00"), "BRL"),),
                policy=policy(allow_rewards=True),
            ),
        )

        assert result.deferred_rewards[0].amount == Decimal("5.00")

    def test_an_unknown_monthly_cap_gives_no_exact_reward(self) -> None:
        """Unless the scenario assumes the whole cap is free."""
        capped = revision(
            1,
            effect(
                "cashback",
                stage="reward",
                reward=RewardTermsFact(
                    credited_as="money",
                    rate=Decimal(5),
                    cap=Decimal(30),
                    cap_period="month",
                ),
            ),
        )
        rewards = policy(allow_rewards=True)

        unknown = evaluate(inputs(revisions=(capped,), policy=rewards))
        assumed = evaluate(
            inputs(revisions=(capped,), policy=replace(rewards, assume_full_caps=True)),
        )

        assert unknown.deferred_rewards[0].amount is None
        assert assumed.deferred_rewards[0].amount == Decimal("5.00")
        assert assumed.assumptions

    def test_points_are_not_money(self) -> None:
        """One point per real, in its own unit."""
        points = revision(
            1,
            effect(
                "points",
                stage="reward",
                params={"per_currency_unit": "1"},
                reward=RewardTermsFact(credited_as="points"),
            ),
        )
        result = evaluate(
            inputs(revisions=(points,), policy=policy(allow_rewards=True))
        )

        assert result.deferred_rewards[0].credited_as == "points"
        assert result.deferred_rewards[0].amount == Decimal(100)
        assert result.merchandise_total == Decimal("100.00")

    def test_a_subscription_prices_a_known_horizon(self) -> None:
        """First delivery 20% off, then 10% off, for three deliveries."""
        plan = revision(
            1,
            effect(
                "subscription",
                stage="catalog",
                params={
                    "interval_days": 30,
                    "first_delivery_rate": "20",
                    "recurring_rate": "10",
                    "minimum_deliveries": 3,
                },
            ),
        )
        result = evaluate(
            inputs(
                revisions=(plan,),
                context=context(subscription=True),
                policy=policy(allow_conditions=frozenset({"subscription"})),
            ),
        )

        assert result.merchandise_total == Decimal("80.00")
        assert [p.amount for p in result.payment_schedule] == [
            Decimal("80.00"),
            Decimal("90.00"),
            Decimal("90.00"),
        ]

    def test_same_inputs_give_the_same_result(self) -> None:
        """Deterministic, and the fingerprint changes with now."""
        same = inputs()
        first = evaluate(same)
        again = evaluate(same)
        later = replace(same, context=context(now=NOW + timedelta(minutes=1)))

        assert first == again
        assert fingerprint(later) != first.input_fingerprint


class GlobalTests(SimpleTestCase):
    """SYNTHETIC: currencies, destinations and markets beyond Brazil."""

    def test_a_currency_without_cents_rounds_to_units(self) -> None:
        """10% off CLP 9,990 is CLP 999, charged as CLP 8,991."""
        promo = revision(1, effect("percentage", params={"rate": "10"}), currency="CLP")
        result = evaluate(
            inputs(
                prices=(price(1, "9990", currency="CLP"),),
                revisions=(promo,),
                context=replace(context(), currency="CLP", minor_unit=0),
            ),
        )

        assert result.merchandise_total == Decimal(8991)
        assert result.adjustments[0].amount == Decimal(999)

    def test_an_alphanumeric_postal_code_matches_its_prefix(self) -> None:
        """No Brazilian eight-digit rule: SW1A 1AA is inside SW1."""
        london = revision(
            1,
            effect("percentage", params={"rate": "10"}),
            conditions={
                "root": {
                    "kind": "destination",
                    "country": "GB",
                    "postal_prefixes": ["SW1"],
                },
            },
        )
        allowed = policy(allow_conditions=frozenset({"destination"}))

        inside = evaluate(
            inputs(
                revisions=(london,),
                policy=allowed,
                context=context(destination=Destination("GB", postal_code="SW1A 1AA")),
            ),
        )
        unknown = evaluate(
            inputs(
                revisions=(london,),
                policy=allowed,
                context=context(destination=Destination("GB")),
            ),
        )

        assert inside.merchandise_total == Decimal("90.00")
        assert unknown.merchandise_total == Decimal("100.00")
        assert DecisionStatus.UNKNOWN in _statuses(unknown)["revision 1"]

    def test_a_price_in_another_currency_is_never_compared(self) -> None:
        """USD 30 is not BRL 30."""
        result = evaluate(inputs(prices=(price(1, "30.00", currency="USD"),)))

        assert result.merchandise_total is None

    def test_an_offer_of_another_market_is_refused(self) -> None:
        """A ranking is per market."""
        result = evaluate(inputs(offers=(replace(offer(), market_id=2),)))

        assert DecisionStatus.INELIGIBLE in _statuses(result)["offer 1"]


class RestrictedPriceTests(SimpleTestCase):
    """R04: a restricted observation is never one unit's public price."""

    def _with(self, **restriction: object) -> object:
        return evaluate(
            inputs(prices=(price(1, "100.00"), price(1, "1.00", **restriction))),
        )

    def test_restrictions_keep_the_public_price(self) -> None:
        """Quantity range, order basis, cart stage and observed contexts."""
        for restriction in (
            {"quantity_min": 10},
            {"amount_basis": "order"},
            {"capture_stage": "cart"},
            {"context": (("destination", "01310"),)},
            {"context": (("membership", "prime"),)},
        ):
            with self.subTest(restriction):
                result = self._with(**restriction)
                assert result.merchandise_total == Decimal("100.00")

    def test_a_quantity_price_applies_inside_its_range(self) -> None:
        """Ten units at the R$ 1 bulk price."""
        result = evaluate(
            inputs(
                prices=(price(1, "100.00"), price(1, "1.00", quantity_min=10)),
                context=context(CartLine(1, 10)),
            ),
        )

        assert result.merchandise_total == Decimal("10.00")

    def test_a_contextual_quote_is_not_accepted_by_default(self) -> None:
        """quoted_for_context needs a matching context; public policies refuse it."""
        result = evaluate(
            inputs(
                prices=(
                    price(1, "100.00"),
                    price(1, "1.00", evidence_level="quoted_for_context"),
                ),
            ),
        )

        assert result.merchandise_total == Decimal("100.00")


class CostsAndGroupsTests(SimpleTestCase):
    """Unconsulted taxes are unknown; order terms across groups are unsupported."""

    def test_taxes_not_consulted_leave_the_total_unknown(self) -> None:
        """An empty fee list is zero only when someone checked."""
        shipping = (ShippingFact("all", Decimal("10.00"), "BRL"),)
        unknown = evaluate(inputs(shipping=shipping, fees_status="not_consulted"))
        consulted = evaluate(inputs(shipping=shipping, fees_status="consulted"))

        assert unknown.total_payable is None
        assert "taxes and fees not consulted" in unknown.missing_context
        assert consulted.total_payable == Decimal("110.00")

    def test_order_terms_across_checkout_groups_are_unsupported(self) -> None:
        """A minimum per order is not applied to two separate checkouts."""
        promo = revision(1, effect("percentage", params={"rate": "10"}))
        result = evaluate(
            inputs(
                offers=(offer(1, seller=100), offer(2, seller=200)),
                prices=(price(1, "100.00"), price(2, "100.00")),
                revisions=(promo,),
                context=context(
                    CartLine(1),
                    CartLine(2),
                    groups=(
                        CheckoutGroup("a", frozenset({1})),
                        CheckoutGroup("b", frozenset({2})),
                    ),
                ),
            ),
        )

        assert result.merchandise_total == Decimal("200.00")
        assert DecisionStatus.UNSUPPORTED in _statuses(result)["revision 1"]


class OrderValueShippingTests(SimpleTestCase):
    """A06: shipping priced for one order value does not hold for another."""

    def test_a_discount_that_changes_the_order_value_drops_the_quote(self) -> None:
        """Quoted for R$ 100; a coupon brings the cart to R$ 90: shipping unknown."""
        quote = ShippingFact("all", Decimal(10), "BRL", order_value=Decimal(100))
        promo = revision(1, effect("fixed_amount", params={"amount": "10"}))

        unchanged = evaluate(inputs(shipping=(quote,)))
        discounted = evaluate(inputs(shipping=(quote,), revisions=(promo,)))

        assert unchanged.shipping_total == Decimal("10.00")
        assert discounted.shipping_total is None
        assert any("order of 100" in item for item in discounted.missing_context)
