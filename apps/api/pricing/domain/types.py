"""The engine's inputs and outputs: immutable, typed, framework-free."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal

ENGINE_VERSION = "1.2.0"


class Tri(StrEnum):
    """A condition holds, does not, or the context cannot tell."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class DecisionStatus(StrEnum):
    """What happened to one candidate."""

    APPLIED = "applied"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    CONFLICT = "conflict"
    STALE = "stale"
    ACCESS_UNAVAILABLE = "access_unavailable"
    INFORMATIVE = "informative"
    NOT_CHOSEN = "not_chosen"


class OptimizationStatus(StrEnum):
    """Whether every allowed combination was evaluated."""

    COMPLETE = "complete"
    BOUNDED = "bounded"


# Facts


@dataclass(frozen=True)
class PriceFact:
    """One observed price of an offer, with what it means."""

    id: int
    offer_id: int
    role: str
    amount: Decimal
    currency: str
    payment_scope: str = "unknown"
    payment_method: str = ""
    installment_count: int | None = None
    installment_amount: Decimal | None = None
    interest: str = "unknown"
    composition: str = "unknown"
    included_adjustments: tuple[str, ...] = ()
    semantics: str = "known"
    evidence_level: str = "observed_in_catalog"
    source_field: str = ""
    observed_at: datetime | None = None
    fresh_until: datetime | None = None
    quantity_min: int = 1
    quantity_max: int | None = None
    amount_basis: str = "unit"
    capture_stage: str = "catalog"
    context: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class OfferFact:
    """An offer as the engine needs it: who sells it, where, and what it is."""

    id: int
    market_id: int
    channel_id: int
    seller_id: int | None
    listing_id: int | None = None
    listing_variant_id: int | None = None
    product_id: int | None = None
    brand_id: int | None = None
    category_ids: frozenset[int] = frozenset()
    merchant_id: int | None = None
    external_categories: frozenset[str] = frozenset()
    purchasable: bool = True
    access_available: bool = True
    seller_is_owner: bool = True


@dataclass(frozen=True)
class RouteFact:
    """A curated way to buy an offer, and what following it preserves."""

    id: int
    offer_id: int
    kind: str
    url: str
    program_id: int | None = None
    fixes_variant: bool = False
    fixes_seller: bool = False
    compatible_programs: frozenset[int] = frozenset()
    instructions: str = ""


@dataclass(frozen=True)
class ShippingFact:
    """A known shipping price for one checkout group, or none."""

    group_key: str
    amount: Decimal | None
    currency: str
    modality: str = ""
    estimate_days: int | None = None
    included_benefits: tuple[str, ...] = ()

    id: int | None = None
    source: str = ""
    observed_at: datetime | None = None
    expires_at: datetime | None = None
    # The order value the carrier priced, when shipping depends on it; the
    # quote holds only for a cart of exactly that value.
    order_value: Decimal | None = None


@dataclass(frozen=True)
class FeeFact:
    """A tax or fee for a checkout group, and whether a price already holds it."""

    group_key: str
    kind: str
    amount: Decimal | None
    currency: str
    included_in_price: bool = False

    # Rules

    id: int | None = None
    source: str = ""
    observed_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class RewardTermsFact:
    """How a deferred reward is credited."""

    credited_as: str
    rate: Decimal | None = None
    cap: Decimal | None = None
    cap_period: str = ""
    minimum: Decimal | None = None
    includes_shipping: bool = False
    eligible_basis: str = "items_after_discounts"
    program_id: int | None = None
    credit_delay_days: int | None = None
    tracking_required: bool = False


@dataclass(frozen=True)
class EffectRule:
    """One effect of a revision."""

    position: int
    kind: str
    stage: str
    basis: str
    target: str
    allocation: str
    params: dict[str, object] = field(default_factory=dict)
    cap: Decimal | None = None
    max_applications: int | None = None
    consumes_units: bool = True
    reward: RewardTermsFact | None = None


@dataclass(frozen=True)
class ScopeRule:
    """One inclusion or exclusion of a revision."""

    role: str
    mode: str
    kind: str
    ref_id: int | None = None
    external_ref: str = ""
    combine: str = "union"


@dataclass(frozen=True)
class CompatibilityFact:
    """Whether a revision combines with another promotion, kind or programme."""

    other_kind: str
    other_ref: str
    verdict: str
    chooser: str = "buyer_choice"


@dataclass(frozen=True)
class RevisionRule:
    """A published revision, as the engine evaluates it."""

    id: int
    promotion_id: int
    number: int
    status: str
    currency: str
    timezone: str
    conditions: dict[str, object]
    effects: tuple[EffectRule, ...]
    scopes: tuple[ScopeRule, ...] = ()
    codes: tuple[tuple[str, str], ...] = ()
    compatibility: tuple[CompatibilityFact, ...] = ()
    ordering: tuple[tuple[int, int], ...] = ()
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    content_hash: str = ""


@dataclass(frozen=True)
class Policy:
    """What a scenario counts, as an immutable policy revision states it."""

    key: str
    version: int
    scenario: str
    objective: str = "items_payable"
    # False: the store's own price, with no promotion, code or reward applied.
    apply_benefits: bool = True
    accepted_semantics: frozenset[str] = frozenset({"known", "legacy_unknown"})
    accepted_evidence: frozenset[str] = frozenset({"observed_in_catalog"})
    cash_methods: frozenset[str] = frozenset({"pix", "boleto"})
    include_unknown_payment: bool = True
    allow_codes: bool = False
    auto_public_codes: bool = False
    allow_private_codes: bool = False
    allow_rewards: bool = False
    allow_conditions: frozenset[str] = frozenset({"min_amount", "min_quantity"})
    net_cost_counts_money_rewards: bool = False
    assume_full_caps: bool = False
    max_combinations: int = 256


# Context


@dataclass(frozen=True)
class CartLine:
    """An offer and how many units of it."""

    offer_id: int
    quantity: int = 1


@dataclass(frozen=True)
class CheckoutGroup:
    """Lines checked out together, as the channel allows."""

    key: str
    offer_ids: frozenset[int]


@dataclass(frozen=True)
class PaymentChoice:
    """How the buyer pays: a method and a number of installments."""

    method: str
    installments: int = 1


@dataclass(frozen=True)
class Destination:
    """Where the order goes. A postal code is text, of any format."""

    country: str
    subdivision: str = ""
    city: str = ""
    postal_code: str = ""


@dataclass(frozen=True)
class Claim:
    """Something the buyer states about themself, with its provenance."""

    kind: str
    issuer: str = ""
    issuer_id: int | None = None
    value: bool = True
    provenance: str = "user"


@dataclass(frozen=True)
class PurchaseContext:
    """Everything that defines one scenario of one purchase."""

    now: datetime
    market_id: int
    currency: str
    minor_unit: int
    lines: tuple[CartLine, ...]
    groups: tuple[CheckoutGroup, ...] = ()
    payment: PaymentChoice | None = None
    destination: Destination | None = None
    codes: frozenset[str] = frozenset()
    programs: frozenset[int] = frozenset()
    claims: tuple[Claim, ...] = ()
    subscription: bool | None = None


# Results


@dataclass(frozen=True)
class Adjustment:
    """One immediate effect, with what it was computed on."""

    revision_id: int
    effect_position: int
    kind: str
    stage: str
    basis_amount: Decimal
    amount: Decimal
    allocations: tuple[tuple[int, Decimal], ...] = ()
    order: int = 0


@dataclass(frozen=True)
class DeferredReward:
    """A reward received later: money, restricted credit or points."""

    revision_id: int
    credited_as: str
    amount: Decimal | None
    unit: str
    basis_amount: Decimal | None
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gift:
    """A gift; it has no money value."""

    revision_id: int
    description: str
    quantity: int
    listing_variant_id: int | None = None


@dataclass(frozen=True)
class ScheduledPayment:
    """One payment of a schedule: when, and how much."""

    sequence: int
    amount: Decimal
    due: str


@dataclass(frozen=True)
class ChosenRoute:
    """How to buy one line so the priced scenario holds, or why it may not."""

    offer_id: int
    route_id: int | None
    url: str | None
    fixes_seller: bool
    reason: str
    fixes_variant: bool = False
    instructions: str = ""


@dataclass(frozen=True)
class Decision:
    """What happened to one candidate, and why."""

    subject: str
    status: DecisionStatus
    reason: str


@dataclass(frozen=True)
class SelectedPrice:
    """The base price chosen for one line."""

    offer_id: int
    observation_id: int
    amount: Decimal
    payment_method: str
    payment_scope: str
    installment_count: int | None
    already_included: tuple[str, ...]


@dataclass(frozen=True)
class PricingResult:
    """The outcome of one scenario, every component explicit."""

    scenario: str
    currency: str
    lines: tuple[CartLine, ...]
    selected_prices: tuple[SelectedPrice, ...]
    payment: PaymentChoice | None
    merchandise_total: Decimal | None
    shipping_total: Decimal | None
    tax_fee_total: Decimal | None
    total_payable: Decimal | None
    due_now: Decimal | None
    payment_schedule: tuple[ScheduledPayment, ...]
    adjustments: tuple[Adjustment, ...]
    deferred_rewards: tuple[DeferredReward, ...]
    gifts: tuple[Gift, ...]
    estimated_net_cost: Decimal | None
    decisions: tuple[Decision, ...]
    assumptions: tuple[str, ...]
    missing_context: tuple[str, ...]
    applied_revisions: tuple[int, ...]
    purchase_routes: tuple[ChosenRoute, ...]
    route_limitations: tuple[str, ...]
    input_fingerprint: str
    engine_version: str
    policy_key: str
    policy_version: int
    evaluated_at: datetime
    expires_at: datetime | None
    optimization_status: OptimizationStatus
