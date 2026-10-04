"""Match qualification and benefit scopes independently, including exclusions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .types import OfferFact, RevisionRule


def _matches(
    scope_kind: str, ref_id: int | None, external: str, offer: OfferFact
) -> bool:
    values = {
        "offer": offer.id,
        "listing": offer.listing_id,
        "listing_variant": offer.listing_variant_id,
        "seller_account": offer.seller_id,
        "market": offer.market_id,
        "channel": offer.channel_id,
        "product": offer.product_id,
        "brand": offer.brand_id,
        "merchant": offer.merchant_id,
    }
    if scope_kind == "category":
        return ref_id in offer.category_ids
    if scope_kind == "external_category":
        return external in offer.external_categories
    return values.get(scope_kind) == ref_id and ref_id is not None


def in_role(revision: RevisionRule, role: str, offer: OfferFact) -> bool | None:
    """Whether an offer is in a role's scope; None when the role names nothing."""
    rows = [scope for scope in revision.scopes if scope.role == role]
    if not rows:
        return None
    for scope in rows:
        if scope.mode == "exclude" and _matches(
            scope.kind, scope.ref_id, scope.external_ref, offer
        ):
            return False
    includes = [scope for scope in rows if scope.mode == "include"]
    if not includes:
        return True
    by_kind: dict[str, bool] = {}
    for scope in includes:
        hit = _matches(scope.kind, scope.ref_id, scope.external_ref, offer)
        by_kind[scope.kind] = by_kind.get(scope.kind, False) or hit
    if any(scope.combine == "intersection" for scope in includes):
        return all(by_kind.values())
    return any(by_kind.values())


def targets(revision: RevisionRule, offer: OfferFact) -> bool:
    """Whether the revision's benefit reaches an offer."""
    return bool(in_role(revision, "target", offer))


def qualifies(revision: RevisionRule, offer: OfferFact) -> bool:
    """Whether an offer counts toward the revision's conditions."""
    explicit = in_role(revision, "qualification", offer)
    return targets(revision, offer) if explicit is None else explicit


def reaching(
    revisions: tuple[RevisionRule, ...],
    offers: Iterable[OfferFact],
) -> tuple[RevisionRule, ...]:
    """Keep the revisions whose benefit reaches at least one of these offers.

    The same scope matching the engine applies decides, so a revision that
    could apply to an offer is never dropped; the rest cannot change any of
    their prices.
    """
    pool = list(offers)
    return tuple(
        revision
        for revision in revisions
        if any(targets(revision, offer) for offer in pool)
    )
