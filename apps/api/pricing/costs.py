"""Select current versions of shipping alternatives and independent charges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import F, OuterRef, Q, Subquery

from .domain.types import FeeFact, ShippingFact
from .models import ShippingQuote, TaxFeeQuote

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class CostBook:
    """Shipping and fees of many checkout groups, read in one pass.

    A projection refresh prices hundreds of single-offer groups; reading
    their costs once keeps the number of queries independent of their count.
    """

    shipping: dict[str, ShippingFact]
    fees: dict[str, list[TaxFeeQuote]]

    @classmethod
    def load(cls, group_keys: list[str], now: datetime) -> CostBook:
        """Read the current costs of every group."""
        shipping, fees = cls._current_costs(group_keys, now)
        by_group: dict[str, list[TaxFeeQuote]] = {}
        for fee in fees:
            by_group.setdefault(fee.group_fingerprint, []).append(fee)
        return cls(shipping={fact.group_key: fact for fact in shipping}, fees=by_group)

    def for_groups(
        self,
        group_keys: list[str],
        tax_inclusion: str,
    ) -> tuple[tuple[ShippingFact, ...], tuple[FeeFact, ...], str]:
        """Return what the engine reads for these groups."""
        fees = [fee for key in group_keys for fee in self.fees.get(key, [])]
        return (
            tuple(self.shipping[key] for key in group_keys if key in self.shipping),
            tuple(self._fee_fact(fee) for fee in fees if fee.kind != "none"),
            self._status(fees, tax_inclusion),
        )

    @staticmethod
    def _status(fees: list[TaxFeeQuote], tax_inclusion: str) -> str:
        """Say how much is known about a group's taxes and fees.

        Only a reading that covered every charge, or a market whose prices
        include taxes, makes the sum known; one fee read proves nothing about
        the others.
        """
        if tax_inclusion == "included":
            return "included_in_prices"
        if any(fee.covers_all_charges for fee in fees):
            return "consulted"
        if fees:
            return "partial"
        return "inclusion_unknown" if tax_inclusion == "unknown" else "not_consulted"

    @staticmethod
    def _current_costs(
        group_keys: list[str],
        now: datetime,
    ) -> tuple[list[ShippingFact], list[TaxFeeQuote]]:
        """Choose latest readings; keep older quotes only with a booking guarantee."""
        latest_shipping = ShippingQuote.objects.filter(
            group_fingerprint=OuterRef("group_fingerprint"),
            seller_account_id=OuterRef("seller_account_id"),
            source=OuterRef("source"),
            modality=OuterRef("modality"),
            currency_id=OuterRef("currency_id"),
            observed_at__lte=now,
        ).order_by("-observed_at", "-pk")
        shipping = (
            ShippingQuote.objects.filter(
                group_fingerprint__in=group_keys,
                observed_at__lte=now,
            )
            .annotate(latest_id=Subquery(latest_shipping.values("pk")[:1]))
            .filter(
                Q(pk=F("latest_id"))
                | (Q(execution_guaranteed=True) & ~Q(external_quote_id="")),
                expires_at__gt=now,
            )
            .order_by(
                "group_fingerprint", "currency_id", "amount", "-observed_at", "-pk"
            )
        )
        cheapest: dict[tuple[str, str], ShippingFact] = {}
        for quote in shipping:
            key = (quote.group_fingerprint, quote.currency_id)
            cheapest.setdefault(
                key,
                ShippingFact(
                    group_key=quote.group_fingerprint,
                    amount=quote.amount,
                    currency=quote.currency_id,
                    modality=quote.modality,
                    estimate_days=quote.estimate_days,
                    included_benefits=tuple(quote.included_benefits or ()),
                    id=quote.pk,
                    source=quote.source,
                    observed_at=quote.observed_at,
                    expires_at=quote.expires_at,
                    order_value=quote.order_value,
                ),
            )
        latest_fee = TaxFeeQuote.objects.filter(
            group_fingerprint=OuterRef("group_fingerprint"),
            source=OuterRef("source"),
            kind=OuterRef("kind"),
            charge_key=OuterRef("charge_key"),
            currency_id=OuterRef("currency_id"),
            observed_at__lte=now,
        ).order_by("-observed_at", "-pk")
        fees = list(
            TaxFeeQuote.objects.filter(
                group_fingerprint__in=group_keys,
                observed_at__lte=now,
            ).filter(pk=Subquery(latest_fee.values("pk")[:1]), expires_at__gt=now),
        )
        return list(cheapest.values()), fees

    @staticmethod
    def _fee_fact(quote: TaxFeeQuote) -> FeeFact:
        """Translate a fee row into what the engine reads."""
        return FeeFact(
            group_key=quote.group_fingerprint,
            kind=quote.kind,
            amount=quote.amount if quote.inclusion != "unknown" else None,
            currency=quote.currency_id,
            included_in_price=quote.inclusion == "included",
            id=quote.pk,
            source=quote.source,
            observed_at=quote.observed_at,
            expires_at=quote.expires_at,
        )
