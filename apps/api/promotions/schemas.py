"""Typed documents a promotion revision stores: its conditions and parameters.

A condition tree is data: ``all``, ``any`` and ``not`` over a closed set of
leaves. Nothing in it is ever executed. Depth and size are capped so a tree
coming from an agent or a page cannot grow without bound.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from .rules.effects import CAPPED_EFFECTS, LIMITED_EFFECTS

MAX_DEPTH = 5
MAX_NODES = 50

# Keep Decimal in runtime globals: Pydantic resolves annotations at import time.
_PYDANTIC_RUNTIME_TYPES = (Decimal,)

Money = Annotated[Decimal, Field(ge=0, max_digits=19, decimal_places=6)]
Rate = Annotated[Decimal, Field(gt=0, le=100, max_digits=9, decimal_places=6)]


class _Closed(BaseModel):
    """A document with no unknown keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# Where a minimum is measured: which items, before or after which discounts,
# with or without shipping. "Minimum R$ 200" alone is not executable.
AmountBasis = Literal[
    "before_discounts",
    "after_item_discounts",
    "after_order_discounts",
]
AmountScope = Literal["qualifying_items", "order", "checkout_group", "seller"]


class MinAmount(_Closed):
    """A minimum spend, with its basis."""

    kind: Literal["min_amount"]
    amount: Money
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    basis: AmountBasis
    scope: AmountScope
    includes_shipping: bool = False


class MinQuantity(_Closed):
    """A minimum number of units."""

    kind: Literal["min_quantity"]
    quantity: int = Field(ge=1)
    scope: AmountScope


class ChannelIn(_Closed):
    """Bought on one of these channels."""

    kind: Literal["channel"]
    channel_ids: list[int] = Field(min_length=1)


class MarketIn(_Closed):
    """Bought in one of these markets."""

    kind: Literal["market"]
    market_ids: list[int] = Field(min_length=1)


class SellerIn(_Closed):
    """Sold by one of these seller accounts."""

    kind: Literal["seller"]
    seller_account_ids: list[int] = Field(min_length=1)


class Destination(_Closed):
    """Delivered to a country, subdivision or postal code prefix."""

    kind: Literal["destination"]
    country: str = Field(pattern=r"^[A-Z]{2}$")
    subdivisions: list[str] = Field(default_factory=list)
    postal_prefixes: list[str] = Field(default_factory=list)


class PaymentMethodIn(_Closed):
    """Paid with one of these methods."""

    kind: Literal["payment_method"]
    codes: list[str] = Field(min_length=1)
    max_installments: int | None = Field(default=None, ge=1)


class ProgramMember(_Closed):
    """The buyer belongs to a programme."""

    kind: Literal["program_member"]
    program_id: int


class Subscription(_Closed):
    """The purchase is, or is not, a subscription."""

    kind: Literal["subscription"]
    required: bool = True


class NewCustomer(_Closed):
    """The buyer is new to an issuer: the channel, a seller or a programme."""

    kind: Literal["new_customer"]
    issuer: Literal["channel", "seller", "program"]
    issuer_id: int


class Calendar(_Closed):
    """On these weekdays, between these local times."""

    kind: Literal["calendar"]
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=list)
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class CodeRequired(_Closed):
    """An activation code must be entered."""

    kind: Literal["code_required"]


Leaf = Annotated[
    MinAmount
    | MinQuantity
    | ChannelIn
    | MarketIn
    | SellerIn
    | Destination
    | PaymentMethodIn
    | ProgramMember
    | Subscription
    | NewCustomer
    | Calendar
    | CodeRequired,
    Field(discriminator="kind"),
]


class AllOf(_Closed):
    """Every child holds."""

    all: list[Condition] = Field(min_length=1)


class AnyOf(_Closed):
    """At least one child holds."""

    any: list[Condition] = Field(min_length=1)


class NotOf(_Closed):
    """The child does not hold."""

    not_: Condition = Field(alias="not")

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


Condition = AllOf | AnyOf | NotOf | Leaf

AllOf.model_rebuild()
AnyOf.model_rebuild()
NotOf.model_rebuild()


class ConditionTree(_Closed):
    """The root of a revision's conditions; ``None`` means unconditional."""

    root: Condition | None = None

    @model_validator(mode="after")
    def _bounded(self) -> ConditionTree:
        """Refuse trees deeper or larger than the caps."""
        depth, nodes = _measure(self.root)
        if depth > MAX_DEPTH:
            msg = f"Conditions nest {depth} levels; at most {MAX_DEPTH}."
            raise ValueError(msg)
        if nodes > MAX_NODES:
            msg = f"Conditions have {nodes} nodes; at most {MAX_NODES}."
            raise ValueError(msg)
        return self


def _measure(node: Condition | None, depth: int = 1) -> tuple[int, int]:
    """Return the depth and node count of a condition tree."""
    if node is None:
        return 0, 0
    children: list[Condition]
    if isinstance(node, AllOf):
        children = node.all
    elif isinstance(node, AnyOf):
        children = node.any
    elif isinstance(node, NotOf):
        children = [node.not_]
    else:
        return depth, 1
    measures = [_measure(child, depth + 1) for child in children]
    return max(d for d, _ in measures), 1 + sum(n for _, n in measures)


def leaves(node: Condition | None) -> list[Leaf]:
    """Return every leaf of a tree, in order."""
    if node is None:
        return []
    if isinstance(node, AllOf):
        return [leaf for child in node.all for leaf in leaves(child)]
    if isinstance(node, AnyOf):
        return [leaf for child in node.any for leaf in leaves(child)]
    if isinstance(node, NotOf):
        return leaves(node.not_)
    return [node]


# Effect parameters, one document per effect kind.


class PercentageParams(_Closed):
    """A percentage off the basis."""

    rate: Rate


class FixedAmountParams(_Closed):
    """A fixed amount off the basis."""

    amount: Money


class FixedPriceParams(_Closed):
    """The target is sold at this price."""

    price: Money


class ShippingDiscountParams(_Closed):
    """Free shipping, a rate or an amount off shipping."""

    free: bool = False
    rate: Rate | None = None
    amount: Money | None = None

    @model_validator(mode="after")
    def _one_form(self) -> ShippingDiscountParams:
        """Exactly one of free, rate or amount."""
        forms = [self.free, self.rate is not None, self.amount is not None]
        if sum(bool(form) for form in forms) != 1:
            msg = "A shipping discount is free, a rate or an amount: exactly one."
            raise ValueError(msg)
        return self


class CashbackParams(_Closed):
    """Cashback; its terms live in the effect's reward terms."""


class PointsParams(_Closed):
    """Points per currency unit spent, or a fixed number of points."""

    per_currency_unit: Decimal | None = Field(default=None, gt=0)
    points: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _one_form(self) -> PointsParams:
        """Exactly one form."""
        if (self.per_currency_unit is None) == (self.points is None):
            msg = "Points are per currency unit or a fixed number: exactly one."
            raise ValueError(msg)
        return self


class GiftParams(_Closed):
    """A gift: which unit, how many. A gift has no money value."""

    listing_variant_id: int | None = None
    description: str = ""
    quantity: int = Field(default=1, ge=1)


class MultibuyParams(_Closed):
    """Buy ``buy``, pay ``pay``; which units are free."""

    buy: int = Field(ge=2)
    pay: int = Field(ge=1)
    free_unit: Literal["cheapest", "most_expensive"] = "cheapest"
    repeat: bool = True

    @model_validator(mode="after")
    def _pays_less(self) -> MultibuyParams:
        """Paying for every unit is not a promotion."""
        if self.pay >= self.buy:
            msg = "A multibuy pays for fewer units than it takes."
            raise ValueError(msg)
        return self


class Tier(_Closed):
    """From a quantity on, a rate or an amount per unit."""

    min_quantity: int = Field(ge=1)
    rate: Rate | None = None
    amount_off_per_unit: Money | None = None

    @model_validator(mode="after")
    def _one_form(self) -> Tier:
        """Exactly one form."""
        if (self.rate is None) == (self.amount_off_per_unit is None):
            msg = "A tier takes a rate or an amount per unit: exactly one."
            raise ValueError(msg)
        return self


class TieredParams(_Closed):
    """Quantity tiers; the highest reached applies."""

    tiers: list[Tier] = Field(min_length=1)

    @model_validator(mode="after")
    def _ascending(self) -> TieredParams:
        """Tiers rise strictly by quantity."""
        quantities = [tier.min_quantity for tier in self.tiers]
        if quantities != sorted(set(quantities)):
            msg = "Tiers rise strictly by minimum quantity."
            raise ValueError(msg)
        return self


class SubscriptionParams(_Closed):
    """A subscription: a first price, a recurring rate, a known schedule."""

    interval_days: int = Field(ge=1)
    first_delivery_rate: Rate | None = None
    recurring_rate: Rate | None = None
    minimum_deliveries: int = Field(default=1, ge=1)


EFFECT_PARAMS: dict[str, type[_Closed]] = {
    "percentage": PercentageParams,
    "fixed_amount": FixedAmountParams,
    "fixed_price": FixedPriceParams,
    "shipping_discount": ShippingDiscountParams,
    "cashback": CashbackParams,
    "points": PointsParams,
    "gift": GiftParams,
    "multibuy": MultibuyParams,
    "tiered": TieredParams,
    "subscription": SubscriptionParams,
}

# Which effect kinds the engine limits by a monetary cap, and by a maximum
# number of applications. A revision setting either on another kind is
# refused at publication: the engine would ignore it.


# Effects whose amounts are money of the revision's currency.
MONETARY_EFFECTS = frozenset({"fixed_amount", "fixed_price"})


class PrecedenceEdge(_Closed):
    """The effect at position ``before`` is computed before ``after``."""

    before: int
    after: int


ORDERING = TypeAdapter(list[PrecedenceEdge])

__all__ = ["CAPPED_EFFECTS", "LIMITED_EFFECTS"]
