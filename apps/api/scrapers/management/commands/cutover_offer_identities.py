"""Preview or apply the legacy product-ID to buyable-unit-ID cutover."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import ProductStore
from offers.models import Offer, StockStatus
from scrapers.models import ScrapedItem


@dataclass(frozen=True)
class CutoverDecision:
    """One legacy offer's verified target, or why it cannot be mapped."""

    offer_id: int
    store_slug: str
    old_id: str
    target_id: str | None
    reason: str


def _candidate_ids(item: ScrapedItem) -> list[tuple[str, str]]:
    """Read unit IDs and SKUs from source evidence, never from a name guess."""
    page = item.source_page
    if page is None or not isinstance(page.api_context, dict):
        return []
    context = page.api_context
    platform = str(context.get("platform") or "")
    product = context.get("product")
    if not isinstance(product, dict):
        return []
    if platform == "shopify":
        product_id = product.get("id")
        units = context.get("variants")
        sku_key = "sku"
        id_key = "id"
    elif platform in {"vtex_legacy", "vtex_graphql", "vtex"}:
        product_id = product.get("productId")
        units = context.get("items")
        sku_key = "itemId"
        id_key = "itemId"
    else:
        return []
    if str(product_id or "") != item.offer.pid:
        return []
    if not isinstance(units, list):
        return []
    return [
        (str(unit.get(id_key) or ""), str(unit.get(sku_key) or ""))
        for unit in units
        if isinstance(unit, dict) and unit.get(id_key)
    ]


def _decide(item: ScrapedItem) -> CutoverDecision:
    """Map only a uniquely evidenced unit; otherwise require archival review."""
    offer = item.offer
    candidates = _candidate_ids(item)
    matches = [unit_id for unit_id, sku in candidates if offer.sku and sku == offer.sku]
    if len(matches) == 1:
        target = matches[0]
        reason = "matched SKU in the source payload"
    elif len(candidates) == 1:
        target = candidates[0][0]
        reason = "the source payload lists exactly one unit"
    else:
        target = None
        reason = "no unique unit identity in the source payload"
    if target and target != offer.external_id:
        existing = Offer.objects.filter(
            store_slug=offer.store_slug,
            external_id=target,
        ).first()
        if existing is not None and existing.pid and existing.pid != offer.pid:
            target = None
            reason = "unit ID already belongs to a different product"
        elif (
            existing is not None
            and ProductStore.objects.filter(offer=offer).exists()
            and ProductStore.objects.filter(offer=existing).exists()
        ):
            target = None
            reason = "both legacy and unit offers already have curated links"
    return CutoverDecision(
        offer.pk, offer.store_slug, offer.external_id, target, reason
    )


@transaction.atomic
def _apply_cutover(decisions: list[CutoverDecision]) -> None:
    """Transfer curated links and archive old rows without moving observations."""
    cutover_at = timezone.now()
    for decision in decisions:
        old = Offer.objects.select_for_update().get(pk=decision.offer_id)
        target = (
            Offer.objects.filter(
                store_slug=old.store_slug,
                external_id=decision.target_id,
            ).first()
            if decision.target_id and decision.target_id != old.external_id
            else None
        )
        if target is None and decision.target_id:
            target = Offer.objects.create(
                store_slug=old.store_slug,
                external_id=decision.target_id,
                pid=old.pid,
                current_price=None,
                current_stock_status=StockStatus.OUT_OF_STOCK,
                current_stock_quantity=0,
            )

        linked = ProductStore.objects.filter(offer=old)
        if (
            target is not None
            and not ProductStore.objects.filter(offer=target).exists()
        ):
            linked.update(offer=target)
        else:
            linked.update(offer=None)
        Offer.objects.filter(pk=old.pk).update(
            delisted_at=cutover_at,
            current_price=None,
            current_stock_status=StockStatus.OUT_OF_STOCK,
            current_stock_quantity=0,
        )


class Command(BaseCommand):
    """Safely prepare legacy offers for variant-level scraping."""

    help = (
        "Preview legacy offer identity changes. --apply writes verified mappings; "
        "--archive-ambiguous explicitly archives unresolved offers."
    )

    def add_arguments(self, parser: object) -> None:
        """Keep all writes behind an explicit operator choice."""
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--archive-ambiguous", action="store_true")

    def handle(self, *args: object, **options: object) -> None:
        """Report decisions, then apply all-or-nothing when explicitly requested."""
        _ = args
        apply = bool(options["apply"])
        archive_ambiguous = bool(options["archive_ambiguous"])
        if archive_ambiguous and not apply:
            message = "--archive-ambiguous requires --apply"
            raise CommandError(message)

        items = (
            ScrapedItem.objects.filter(
                offer__external_id=F("offer__pid"),
                offer__delisted_at__isnull=True,
            )
            .exclude(offer__pid="")
            .select_related("offer", "source_page")
        )
        decisions = []
        for item in items:
            if isinstance(item.variant_context, dict) and item.variant_context.get(
                "provider_variant_id"
            ):
                continue
            decision = _decide(item)
            if decision.target_id != decision.old_id:
                decisions.append(decision)
        for decision in decisions:
            self.stdout.write(
                f"{decision.store_slug}/{decision.old_id}: "
                f"{decision.target_id or 'AMBIGUOUS'} ({decision.reason})"
            )
        ambiguous = [decision for decision in decisions if decision.target_id is None]
        self.stdout.write(
            f"{len(decisions)} legacy offers; {len(ambiguous)} ambiguous; "
            f"{'applying' if apply else 'preview only'}"
        )
        if not apply:
            return
        if ambiguous and not archive_ambiguous:
            message = (
                "Ambiguous offers found; review them, then use "
                "--archive-ambiguous to detach and archive them."
            )
            raise CommandError(message)

        _apply_cutover(decisions)
