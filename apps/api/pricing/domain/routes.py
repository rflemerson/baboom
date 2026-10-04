"""Choose the purchase route of each line, and what tracking survives it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .types import (
    ChosenRoute,
)

if TYPE_CHECKING:
    from .application import Outcome
    from .inputs import Inputs
    from .types import (
        RouteFact,
    )

ROUTE_PREFERENCE = ("direct", "affiliate", "marketplace_listing")


def chosen_routes(
    inputs: Inputs,
    outcome: Outcome,
) -> tuple[tuple[ChosenRoute, ...], tuple[str, ...]]:
    """Choose how to buy each line, and say where a link may not hold.

    A route a reward required wins; otherwise the curated direct, affiliate
    or listing route, preferring one that opens the exact variant. A line
    with none keeps the offer's own link. A third-party seller's offer whose
    link does not fix the seller is reported: the page may sell another's.
    """
    offers = {offer.id: offer for offer in inputs.offers}
    chosen: list[ChosenRoute] = []
    limitations: list[str] = []
    for line in inputs.context.lines:
        route = outcome.routes.get(line.offer_id) or _curated_route(
            inputs, line.offer_id
        )
        offer = offers.get(line.offer_id)
        fixes_seller = bool(route and route.fixes_seller) or bool(
            offer and offer.seller_is_owner,
        )
        reason = (
            "required by a reward"
            if line.offer_id in outcome.routes
            else ("curated route" if route else "the offer's own link")
        )
        chosen.append(
            ChosenRoute(
                offer_id=line.offer_id,
                route_id=route.id if route else None,
                url=route.url if route else None,
                fixes_seller=fixes_seller,
                reason=reason,
                fixes_variant=bool(route and route.fixes_variant),
                instructions=route.instructions if route else "",
            ),
        )
        if not fixes_seller:
            limitations.append(
                f"the link to offer {line.offer_id} may open another seller",
            )
    return tuple(chosen), tuple(limitations)


def _curated_route(inputs: Inputs, offer_id: int) -> RouteFact | None:
    candidates = [
        route
        for route in inputs.routes
        if route.offer_id == offer_id and route.kind in ROUTE_PREFERENCE
    ]
    candidates.sort(
        key=lambda route: (
            not route.fixes_variant,
            ROUTE_PREFERENCE.index(route.kind),
            route.id,
        ),
    )
    return candidates[0] if candidates else None
