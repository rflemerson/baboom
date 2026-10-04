"""R06: a reward that needs tracking needs the route that keeps it."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from pricing.domain.engine import evaluate
from pricing.domain.types import DecisionStatus, RewardTermsFact, RouteFact
from pricing.tests.domain.builders import effect, inputs, offer, policy, revision

TRACKED = RewardTermsFact(
    credited_as="money",
    rate=Decimal(10),
    tracking_required=True,
    program_id=7,
)
ACTIVATION = RouteFact(
    id=1,
    offer_id=1,
    kind="cashback_activation",
    url="https://cashback.example/go/1",
    program_id=7,
    fixes_variant=True,
)


def _cashback(*routes: RouteFact) -> object:
    promo = revision(1, effect("cashback", stage="reward", reward=TRACKED))
    return evaluate(
        inputs(revisions=(promo,), policy=policy(allow_rewards=True), routes=routes),
    )


class TrackedCashbackTests(SimpleTestCase):
    """No route, no reward; the route found is the one to follow."""

    def test_no_route_means_no_reward(self) -> None:
        """R$ 10 on R$ 100 is not promised without the activation link."""
        result = _cashback()

        assert result.deferred_rewards == ()
        assert DecisionStatus.UNKNOWN in {d.status for d in result.decisions}

    def test_a_route_of_another_programme_does_not_count(self) -> None:
        """Programme 8's link does not track programme 7."""
        result = _cashback(RouteFact(**{**ACTIVATION.__dict__, "program_id": 8}))

        assert result.deferred_rewards == ()

    def test_the_activation_route_is_returned_with_the_reward(self) -> None:
        """The buyer is sent through the link that keeps the cashback."""
        result = _cashback(ACTIVATION)

        assert result.deferred_rewards[0].amount == Decimal("10.00")
        route = result.purchase_routes[0]
        assert route.route_id == ACTIVATION.id
        assert route.url == ACTIVATION.url
        assert route.reason == "required by a reward"


class LinkTests(SimpleTestCase):
    """Whether following the link reaches the priced seller."""

    def test_a_third_party_seller_link_is_a_limitation(self) -> None:
        """A VTEX ?skuId= link does not select the seller."""
        result = evaluate(inputs(offers=(offer(seller_is_owner=False),)))

        assert not result.purchase_routes[0].fixes_seller
        assert result.route_limitations

    def test_a_curated_route_that_fixes_the_seller_lifts_it(self) -> None:
        """A marketplace listing link that opens the seller."""
        route = RouteFact(
            id=2,
            offer_id=1,
            kind="marketplace_listing",
            url="https://market.example/item?seller=9",
            fixes_seller=True,
        )
        result = evaluate(
            inputs(offers=(offer(seller_is_owner=False),), routes=(route,))
        )

        assert result.purchase_routes[0].fixes_seller
        assert result.purchase_routes[0].url == route.url
        assert result.route_limitations == ()
