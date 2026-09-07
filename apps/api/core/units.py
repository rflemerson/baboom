"""Unit registry for the quantities the catalog stores and computes with.

Storage is canonical: one base unit per dimension, declared here and nowhere
else. Values are converted on the way in and formatted on the way out, so no
column, annotation, or field name carries a unit of its own.

The base for mass is the milligram rather than the SI kilogram. Every unit this
domain uses -- from the micrograms of a vitamin to the kilograms of a package --
is a power of ten away from it, so conversions stay exact in decimal arithmetic
and stored values stay readable. Energy keeps the kilocalorie the label is
printed in, for the same reason.
"""

from decimal import Decimal
from enum import StrEnum
from typing import NamedTuple


class Dimension(StrEnum):
    """Physical dimensions the catalog measures."""

    MASS = "mass"
    ENERGY = "energy"


class UnitSpec(NamedTuple):
    """A unit and how many canonical units one of it is worth."""

    dimension: Dimension
    factor: Decimal


UNITS: dict[str, UnitSpec] = {
    "kg": UnitSpec(Dimension.MASS, Decimal(1_000_000)),
    "g": UnitSpec(Dimension.MASS, Decimal(1_000)),
    "mg": UnitSpec(Dimension.MASS, Decimal(1)),
    "mcg": UnitSpec(Dimension.MASS, Decimal("0.001")),
    "kcal": UnitSpec(Dimension.ENERGY, Decimal(1)),
}

CANONICAL: dict[Dimension, str] = {
    Dimension.MASS: "mg",
    Dimension.ENERGY: "kcal",
}

DIMENSIONLESS: frozenset[str] = frozenset({"-", "IU", "%"})

DISPLAY_MASS_UNIT = "g"


def is_convertible(unit: str) -> bool:
    """Return whether a unit maps onto a dimension the catalog can convert."""
    return unit in UNITS


def convert(value: Decimal, from_unit: str, to_unit: str) -> Decimal | None:
    """Convert between two units of the same dimension.

    Returns None when either unit is unknown or dimensionless, or when the two
    belong to different dimensions: an unconvertible value is not an error, it
    simply carries no quantity the catalog can rank.
    """
    source = UNITS.get(from_unit)
    target = UNITS.get(to_unit)
    if source is None or target is None or source.dimension != target.dimension:
        return None
    return value * source.factor / target.factor


def to_canonical(value: Decimal, unit: str) -> Decimal | None:
    """Convert a value into the canonical unit of its dimension."""
    spec = UNITS.get(unit)
    if spec is None:
        return None
    return convert(value, unit, CANONICAL[spec.dimension])


def from_canonical(value: Decimal, unit: str) -> Decimal | None:
    """Convert a canonical value into the requested unit of its dimension."""
    spec = UNITS.get(unit)
    if spec is None:
        return None
    return convert(value, CANONICAL[spec.dimension], unit)


def unit_choices() -> list[tuple[str, str]]:
    """Return the selectable units, convertible ones first."""
    return [(unit, unit) for unit in (*UNITS, *sorted(DIMENSIONLESS))]
