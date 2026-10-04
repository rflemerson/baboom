"""Small builders for engine inputs; every value is synthetic and labelled so."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from itertools import count

from pricing.domain.inputs import Inputs
from pricing.domain.types import (
    CartLine,
    EffectRule,
    OfferFact,
    Policy,
    PriceFact,
    PurchaseContext,
    RevisionRule,
    ScopeRule,
)
from promotions.rules.effects import EFFECT_SPECS

NOW = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
MARKET = 1
CHANNEL = 10
_ids = count(1000)


def offer(offer_id: int = 1, seller: int = 100, **kwargs: object) -> OfferFact:
    """Build a purchasable offer of the default market."""
    return OfferFact(
        id=offer_id,
        market_id=MARKET,
        channel_id=CHANNEL,
        seller_id=seller,
        **kwargs,
    )


def price(offer_id: int, amount: str, **kwargs: object) -> PriceFact:
    """Build a payable BRL price; payment unknown unless stated."""
    return PriceFact(
        id=next(_ids),
        offer_id=offer_id,
        role=str(kwargs.pop("role", "payable")),
        amount=Decimal(amount),
        currency=str(kwargs.pop("currency", "BRL")),
        **kwargs,
    )


def _preferred(allowed: frozenset[str], *choices: str) -> str:
    return next((choice for choice in choices if choice in allowed), min(allowed))


def effect(kind: str, position: int = 1, **kwargs: object) -> EffectRule:
    """Build an effect with the settings its handler applies, unless stated."""
    spec = EFFECT_SPECS.get(kind)
    defaults: dict[str, object] = {
        "stage": _preferred(spec.stages, "order") if spec else "order",
        "basis": (
            _preferred(spec.bases, "eligible_subtotal", "current")
            if spec
            else "current"
        ),
        "target": _preferred(spec.targets, "order") if spec else "order",
        "allocation": (
            _preferred(spec.allocations, "prorated", "per_unit") if spec else "prorated"
        ),
        "params": {},
    }
    defaults.update(kwargs)
    return EffectRule(position=position, kind=kind, **defaults)


def revision(revision_id: int, *effects: EffectRule, **kwargs: object) -> RevisionRule:
    """Build an executable BRL revision targeting the market, unconditional."""
    defaults: dict[str, object] = {
        "promotion_id": revision_id,
        "number": 1,
        "status": "executable",
        "currency": "BRL",
        "timezone": "America/Sao_Paulo",
        "conditions": {"root": None},
        "scopes": (
            ScopeRule(role="target", mode="include", kind="market", ref_id=MARKET),
        ),
    }
    defaults.update(kwargs)
    return RevisionRule(id=revision_id, effects=effects, **defaults)


def policy(scenario: str = "listed", **kwargs: object) -> Policy:
    """Build a scenario policy; codes and rewards off unless stated."""
    return Policy(key=f"test-{scenario}", version=1, scenario=scenario, **kwargs)


def context(*lines: CartLine, **kwargs: object) -> PurchaseContext:
    """Build a BRL purchase at NOW."""
    return PurchaseContext(
        now=kwargs.pop("now", NOW),
        market_id=MARKET,
        currency="BRL",
        minor_unit=2,
        lines=lines or (CartLine(1, 1),),
        **kwargs,
    )


def inputs(**kwargs: object) -> Inputs:
    """One offer at R$ 100 in the listed scenario, overridable."""
    base = Inputs(
        context=context(),
        offers=(offer(),),
        prices=(price(1, "100.00"),),
        revisions=(),
        policy=policy(),
        fees_status="included_in_prices",
    )
    return replace(base, **kwargs)
