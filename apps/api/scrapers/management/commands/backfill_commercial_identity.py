"""Preview or apply the commercial identity of offers captured before it existed.

Each offer gets the market its spider declares, a listing and variant read from
its captured page, and a seller only where the captured source names one. A
VTEX offer whose default seller is not in the stored context stays without a
seller and is listed for review: the current default seller is never assumed
to have sold the history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand
from django.db import transaction
from scrapy.spiderloader import SpiderLoader
from scrapy.utils.project import get_project_settings

from commerce.services import CommerceIdentityService, SellerRef
from core.models import Store
from offers.services import (
    ListingRef,
    OfferIdentityRef,
    OfferIdentityService,
    VariantRef,
)
from scrapers.crawler.base import CatalogSpider
from scrapers.models import ScrapedItem
from scrapers.normalizers.vtex import VTEX_CHANNEL_OWNER_SELLER_ID
from scrapers.services import market_ref

if TYPE_CHECKING:
    from argparse import ArgumentParser

    from commerce.models import Market
    from commerce.services import MarketRef

VTEX_PLATFORMS = frozenset({"vtex_legacy", "vtex_graphql"})


@dataclass(frozen=True)
class SellerFinding:
    """The seller the stored context names for one offer, if any."""

    ref: SellerRef | None
    reason: str


def store_markets() -> dict[str, MarketRef]:
    """Return the market each store spider declares, by store slug."""
    settings = get_project_settings()
    settings.setmodule("scrapers.crawler.settings")
    loader = SpiderLoader.from_settings(settings)
    markets: dict[str, MarketRef] = {}
    for name in loader.list():
        spider_class = loader.load(name)
        if not issubclass(spider_class, CatalogSpider) or not spider_class.STORE_SLUG:
            continue
        declared = spider_class().market_input()
        markets[declared.namespace] = market_ref(declared)
    return markets


def _vtex_seller(context: dict, item_id: str) -> SellerFinding:
    """Read the default seller of one SKU from a stored VTEX context."""
    for item in context.get("items") or []:
        if not isinstance(item, dict) or str(item.get("itemId")) != item_id:
            continue
        sellers = [s for s in item.get("sellers") or [] if isinstance(s, dict)]
        chosen = next((s for s in sellers if s.get("sellerDefault")), None)
        chosen = chosen or (sellers[0] if sellers else None)
        if chosen is None or not chosen.get("sellerId"):
            return SellerFinding(None, "no seller in the stored context")
        seller_id = str(chosen["sellerId"])
        return SellerFinding(
            SellerRef(
                external_id=seller_id,
                name=str(chosen.get("sellerName") or ""),
                is_channel_owner=seller_id == VTEX_CHANNEL_OWNER_SELLER_ID,
            ),
            "named by the stored context",
        )
    return SellerFinding(None, "SKU not in the stored context")


def seller_for(item: ScrapedItem) -> SellerFinding:
    """Name the seller the captured source states for an offer, or why not."""
    context = item.source_page.api_context if item.source_page else {}
    platform = str(context.get("platform") or "") if isinstance(context, dict) else ""
    if platform in VTEX_PLATFORMS:
        return _vtex_seller(context, item.offer.external_id)
    if not platform:
        return SellerFinding(None, "no captured context")
    return SellerFinding(
        SellerRef(is_channel_owner=True),
        f"{platform} sells only the store's stock",
    )


class Command(BaseCommand):
    """Backfill listings, variants, sellers and source identities."""

    help = (
        "Preview, or with --apply write, the market, listing, variant, seller "
        "and source identities of offers captured before they existed."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Preview by default."""
        parser.add_argument("--apply", action="store_true")

    def handle(self, *_args: object, **options: object) -> None:
        """Report every decision, and write them only with --apply."""
        apply = bool(options["apply"])
        markets = store_markets()
        unresolved: list[str] = []
        bound = 0
        with transaction.atomic():
            resolved_markets = {
                slug: CommerceIdentityService.market(ref)
                for slug, ref in markets.items()
            }
            items = ScrapedItem.objects.select_related("offer", "source_page")
            for item in items.iterator():
                market = resolved_markets.get(item.offer.store_slug)
                if market is None:
                    unresolved.append(f"{item.offer}: no spider declares its market")
                    continue
                finding = seller_for(item)
                if finding.ref is None:
                    unresolved.append(f"{item.offer}: {finding.reason}")
                self._bind(item, market, finding)
                bound += 1
            stores = self._bind_stores(resolved_markets)
            if not apply:
                transaction.set_rollback(True)
        verb = "Bound" if apply else "Would bind"
        self.stdout.write(f"{verb} {bound} offers and {stores} stores.")
        self.stdout.write(f"Without a seller, for review: {len(unresolved)}")
        for line in unresolved:
            self.stdout.write(f"  {line}")

    @staticmethod
    def _bind(item: ScrapedItem, market: Market, finding: SellerFinding) -> None:
        """Bind one offer from its captured variant context."""
        context = item.variant_context if isinstance(item.variant_context, dict) else {}
        offer = item.offer
        listing_id = str(context.get("provider_product_id") or offer.pid or "")
        variant_id = str(context.get("provider_variant_id") or offer.external_id)
        seller = (
            CommerceIdentityService.seller(market, finding.ref)
            if finding.ref is not None
            else None
        )
        if finding.ref is None:
            seller_key = "unknown"
        elif finding.ref.is_channel_owner:
            seller_key = "owner"
        else:
            seller_key = finding.ref.external_id
        OfferIdentityService().bind(
            offer,
            OfferIdentityRef(
                market=market,
                listing=ListingRef(
                    external_id=listing_id or offer.external_id,
                    url=item.source_page.url if item.source_page else "",
                    title=str(context.get("title") or offer.name),
                ),
                variant=VariantRef(
                    external_id=variant_id,
                    options=tuple(offer.options or ()),
                    selection=context.get("selection") or None,
                    gtin=offer.ean,
                ),
                seller_account=seller,
                scheme=str(context.get("provider") or "legacy-context"),
                key=f"{variant_id}@{seller_key}",
            ),
        )
        if item.source_page and item.source_page.listing_id is None:
            item.source_page.listing = offer.listing_variant.listing
            item.source_page.save(update_fields=["listing", "updated_at"])

    @staticmethod
    def _bind_stores(markets: dict[str, Market]) -> int:
        """Point each catalog store at the owner account of its market."""
        bound = 0
        for store in Store.objects.filter(scraper_slug__in=markets.keys()):
            owner = CommerceIdentityService.seller(
                markets[str(store.scraper_slug)],
                SellerRef(is_channel_owner=True),
            )
            if store.seller_account_id != owner.pk:
                store.seller_account = owner
                store.save(update_fields=["seller_account", "updated_at"])
            bound += 1
        return bound
