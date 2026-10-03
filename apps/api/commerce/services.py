"""Resolve the channel, market and seller account a source speaks for."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from .models import Channel, Currency, Market, SellerAccount


@dataclass(frozen=True)
class MarketRef:
    """What an adapter declares about the market it reads.

    ``provenance`` says how country and currency are known: a store spider
    declares them (``source_contract``); they are not observed in each payload.
    """

    namespace: str
    channel_name: str
    channel_kind: str
    adapter: str
    country: str
    currency: str
    timezone: str
    provenance: str = "source_contract"


@dataclass(frozen=True)
class SellerRef:
    """A seller as the source names it.

    ``external_id`` empty with ``is_channel_owner`` means the channel's own
    store, on a platform without third-party sellers.
    """

    external_id: str = ""
    name: str = ""
    is_channel_owner: bool = False


class CommerceIdentityService:
    """Find or create the commercial identities a crawl writes under."""

    @staticmethod
    @transaction.atomic
    def market(ref: MarketRef) -> Market:
        """Return the market of a namespace, creating its channel the first time.

        An existing market is never re-pointed: a namespace that once meant one
        channel, country and currency keeps meaning it.
        """
        existing = Market.objects.filter(namespace=ref.namespace).first()
        if existing is not None:
            return existing
        channel, _created = Channel.objects.get_or_create(
            name=ref.channel_name,
            defaults={"kind": ref.channel_kind, "adapter": ref.adapter},
        )
        currency = Currency.objects.get(code=ref.currency)
        return Market.objects.create(
            channel=channel,
            country=ref.country,
            currency=currency,
            timezone=ref.timezone,
            namespace=ref.namespace,
            provenance=ref.provenance,
        )

    @staticmethod
    def seller(market: Market, ref: SellerRef) -> SellerAccount:
        """Return the account a source names, by id within its market.

        The channel owner is one account per market. Any other seller is found
        by its external id, never by name; the published name is refreshed.
        """
        if ref.is_channel_owner:
            account, _created = SellerAccount.objects.get_or_create(
                market=market,
                is_channel_owner=True,
                defaults={"external_id": ref.external_id, "name_raw": ref.name},
            )
            if ref.external_id and not account.external_id:
                account.external_id = ref.external_id
                account.save(update_fields=["external_id", "updated_at"])
            return account
        if not ref.external_id:
            msg = "A seller other than the channel owner needs its market id."
            raise ValueError(msg)
        account, created = SellerAccount.objects.get_or_create(
            market=market,
            external_id=ref.external_id,
            defaults={"name_raw": ref.name},
        )
        if not created and ref.name and account.name_raw != ref.name:
            account.name_raw = ref.name
            account.save(update_fields=["name_raw", "updated_at"])
        return account
