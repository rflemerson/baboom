"""Everything one evaluation reads, and its canonical, hashable form."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import (
        FeeFact,
        OfferFact,
        Policy,
        PriceFact,
        PurchaseContext,
        RevisionRule,
        RouteFact,
        ShippingFact,
    )


@dataclass(frozen=True)
class Inputs:
    """Everything one evaluation reads."""

    context: PurchaseContext
    offers: tuple[OfferFact, ...]
    prices: tuple[PriceFact, ...]
    revisions: tuple[RevisionRule, ...]
    policy: Policy
    shipping: tuple[ShippingFact, ...] = ()
    fees: tuple[FeeFact, ...] = ()
    routes: tuple[RouteFact, ...] = ()
    # "included_in_prices": the market's prices carry every tax, so only fees
    # quoted on top are added; "consulted": a source answered for every
    # charge, so ``fees`` is complete (possibly empty); "partial": some
    # charges were read, not all; "not_consulted": nobody asked;
    # "inclusion_unknown": not even whether prices include taxes is known.
    # Only the first two give a known total.
    fees_status: str = "not_consulted"
    # The exact benefits the chosen combination uses, of "coupon" and
    # "cashback": an empty set asks for neither. None takes the best
    # combination whatever it uses.
    benefits: frozenset[str] | None = None


def canonical(value: object) -> object:
    """Turn inputs into JSON-ready data with a stable order."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: canonical(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {
            str(key): canonical(item) for key, item in sorted(value.items(), key=str)
        }
    if isinstance(value, (frozenset, set)):
        return sorted((canonical(item) for item in value), key=str)
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value if isinstance(value, (int, str, bool, type(None))) else str(value)


def fingerprint(inputs: Inputs) -> str:
    """Hash everything an evaluation read, including ``now``."""
    text = json.dumps(canonical(inputs), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()
