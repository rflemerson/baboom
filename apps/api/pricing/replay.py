"""Rebuild a kept quote's inputs from its snapshot and evaluate them again.

A replay reads nothing but the snapshot: no current offer, observation,
promotion or policy. The same snapshot and engine version give the same
result, which is how a quote's explanation is audited after the facts and
rules it used have changed.
"""

from __future__ import annotations

import types
from dataclasses import dataclass, fields, is_dataclass
from dataclasses import field as dataclass_field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Union, get_args, get_origin, get_type_hints

from .domain import engine
from .domain import types as domain_types
from .domain.engine import Inputs, evaluate

if TYPE_CHECKING:
    from collections.abc import Callable

    from .domain.types import PricingResult
    from .models import PricingQuote

NAMESPACE: dict[str, object] = {
    **vars(domain_types),
    **vars(engine),
    "Decimal": Decimal,
    "datetime": datetime,
}


@dataclass(frozen=True)
class ReplayCheck:
    """What replaying a quote showed, and which result fields differ."""

    status: str
    differences: list[str] = dataclass_field(default_factory=list)


class QuoteReplay:
    """Rebuild a quote's inputs from its snapshot and evaluate them again."""

    SCALARS: ClassVar[dict[object, Callable[[object], object]]] = {
        Decimal: lambda value: Decimal(str(value)),
        datetime: lambda value: datetime.fromisoformat(str(value)),
    }

    def replay(self, quote: PricingQuote) -> PricingResult:
        """Evaluate a kept quote again, from its snapshot alone."""
        if quote.snapshot.get("schema_version") != 1:
            msg = "Unsupported snapshot version; use its original engine"
            raise ValueError(msg)
        if quote.engine_version != domain_types.ENGINE_VERSION:
            msg = "Replay requires the original engine version"
            raise ValueError(msg)
        return evaluate(self.inputs(quote.snapshot))

    def check(self, quote: PricingQuote) -> ReplayCheck:
        """Replay a quote and compare the whole result it kept.

        The input fingerprint is left out: the snapshot keeps protected
        inputs, whose fingerprint is ``protected_fingerprint`` instead.
        """
        version = quote.snapshot.get("schema_version")
        if version != 1 or quote.engine_version != domain_types.ENGINE_VERSION:
            return ReplayCheck("other_engine")
        try:
            result = self.replay(quote)
        except KeyError, TypeError, ValueError:
            return ReplayCheck("invalid_snapshot")
        kept = dict(quote.snapshot.get("result") or {})
        again = engine.canonical(result)
        if not isinstance(again, dict):  # pragma: no cover - result is a dataclass
            return ReplayCheck("invalid_snapshot")
        for name in ("input_fingerprint",):
            kept.pop(name, None)
            again.pop(name, None)
        differences = sorted(
            name
            for name in kept.keys() | again.keys()
            if kept.get(name) != again.get(name)
        )
        return ReplayCheck("differs" if differences else "reproduced", differences)

    def inputs(self, snapshot: dict[str, object]) -> Inputs:
        """Rebuild the protected inputs a quote kept."""
        built = self._build(Inputs, snapshot["inputs"])
        if not isinstance(built, Inputs):  # pragma: no cover - snapshot shape
            msg = "The snapshot does not describe pricing inputs."
            raise TypeError(msg)
        return built

    def _build(self, kind: object, value: object) -> object:
        """Rebuild a value of a type from its canonical JSON form."""
        if value is None:
            return None
        origin = get_origin(kind)
        if origin in (Union, types.UnionType):
            options = [arg for arg in get_args(kind) if arg is not type(None)]
            return self._build(options[0], value)
        if is_dataclass(kind) and isinstance(kind, type):
            return self._dataclass(kind, value)
        if origin is tuple:
            return self._tuple(kind, value)
        if origin is frozenset:
            (inner,) = get_args(kind)
            return frozenset(self._build(inner, item) for item in value)
        scalar = self.SCALARS.get(kind)
        return scalar(value) if scalar is not None else value

    def _dataclass(self, kind: type, value: object) -> object:
        hints = get_type_hints(kind, globalns=NAMESPACE)
        data = value if isinstance(value, dict) else {}
        return kind(
            **{
                field.name: self._build(hints[field.name], data[field.name])
                for field in fields(kind)
                if field.name in data
            },
        )

    def _tuple(self, kind: object, value: object) -> tuple:
        args = get_args(kind)
        items = list(value) if isinstance(value, list) else []
        if args and args[-1] is Ellipsis:
            return tuple(self._build(args[0], item) for item in items)
        return tuple(
            self._build(arg, item) for arg, item in zip(args, items, strict=False)
        )
