from datetime import timedelta
from typing import cast

import strawberry
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.models import ScrapedItem

from .types import ScrapedItemType


@strawberry.type
class ScrapersMutation:
    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def checkout_scraped_item(self) -> ScrapedItemType | None:
        """
        Reserves an item for the Agent to process.
        Retrieves NEW items or ERROR items that have 'rested' for 30min (retry threshold).
        """
        now = timezone.now()
        retry_threshold = now - timedelta(minutes=30)

        with transaction.atomic():
            item = (
                ScrapedItem.objects.select_for_update(skip_locked=True)
                .filter(
                    Q(status=ScrapedItem.Status.NEW)
                    | Q(
                        status=ScrapedItem.Status.ERROR,
                        error_count__lt=3,
                        last_attempt_at__lt=retry_threshold,
                    ),
                    product_link__startswith="http",
                )
                .order_by("updated_at")
                .first()
            )

            if item:
                item.status = ScrapedItem.Status.PROCESSING
                item.last_attempt_at = now
                item.save()
                return cast(ScrapedItemType, item)

            return None

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def report_scraped_item_error(
        self, item_id: int, message: str, is_fatal: bool = False
    ) -> bool:
        try:
            item = ScrapedItem.objects.get(id=item_id)

            if is_fatal:
                item.status = ScrapedItem.Status.REVIEW
                item.last_error_log = f"FATAL: {message}"
            else:
                item.status = ScrapedItem.Status.ERROR
                item.error_count += 1
                item.last_error_log = message

                if item.error_count >= 3:
                    item.status = ScrapedItem.Status.REVIEW
                    item.last_error_log += " (Max retries reached)"

            item.save()
            return True
        except ScrapedItem.DoesNotExist:
            return False

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def discard_scraped_item(self, item_id: int, reason: str) -> bool:
        """
        Agent marks item as DISCARDED (e.g., it is a T-shirt, not a supplement).
        """
        try:
            item = ScrapedItem.objects.get(id=item_id)
            item.status = ScrapedItem.Status.DISCARDED
            item.last_error_log = f"Discarded by Agent: {reason}"
            item.save()
            return True
        except ScrapedItem.DoesNotExist:
            return False
