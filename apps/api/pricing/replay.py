"""Rebuild a kept quote's inputs from its snapshot and evaluate them again.

A replay reads nothing but the snapshot: no current offer, observation,
promotion or policy. The same snapshot and engine version give the same
result, which is how a quote's explanation is audited after the facts and
rules it used have changed.
"""

from __future__ import annotations

import types
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Union, get_args, get_origin, get_type_hints

from .domain import engine
from .domain import types as domain_types
from .domain.engine import Inputs, evaluate

if TYPE_CHECKING:
    from .domain.types import PricingResult
    from .models import PricingQuote

NAMESPACE: dict[str, object] = {
    **vars(domain_types),
    **vars(engine),
    "Decimal": Decimal,
    "datetime": datetime,
}


def _build(kind: object, value: object) -> object:
    """Rebuild a value of a type from its canonical JSON form."""
    if value is None:
        return None
    origin = get_origin(kind)
    if origin in (Union, types.UnionType):
        options = [arg for arg in get_args(kind) if arg is not type(None)]
        return _build(options[0], value)
    if is_dataclass(kind) and isinstance(kind, type):
        return _dataclass(kind, value)
    if origin is tuple:
        return _tuple(kind, value)
    if origin is frozenset:
        (inner,) = get_args(kind)
        return frozenset(_build(inner, item) for item in value)
    scalar = SCALARS.get(kind)
    return scalar(value) if scalar is not None else value


def _dataclass(kind: type, value: object) -> object:
    hints = get_type_hints(kind, globalns=NAMESPACE)
    data = value if isinstance(value, dict) else {}
    return kind(
        **{
            field.name: _build(hints[field.name], data[field.name])
            for field in fields(kind)
            if field.name in data
        },
    )


def _tuple(kind: object, value: object) -> tuple:
    args = get_args(kind)
    items = list(value) if isinstance(value, list) else []
    if args and args[-1] is Ellipsis:
        return tuple(_build(args[0], item) for item in items)
    return tuple(_build(arg, item) for arg, item in zip(args, items, strict=False))


SCALARS = {
    Decimal: lambda value: Decimal(str(value)),
    datetime: lambda value: datetime.fromisoformat(str(value)),
}


def inputs_from_snapshot(snapshot: dict[str, object]) -> Inputs:
    """Rebuild the protected inputs a quote kept."""
    built = _build(Inputs, snapshot["inputs"])
    if not isinstance(built, Inputs):  # pragma: no cover - snapshot shape
        msg = "The snapshot does not describe pricing inputs."
        raise TypeError(msg)
    return built


def replay(quote: PricingQuote) -> PricingResult:
    """Evaluate a kept quote again, from its snapshot alone."""
    return evaluate(inputs_from_snapshot(quote.snapshot))
