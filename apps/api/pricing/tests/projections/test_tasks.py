"""The refresh task and the frozen policies it reads."""

from __future__ import annotations

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from common.testing import raised
from pricing.models import OfferScenarioProjection, PricingPolicyRevision
from pricing.tasks import refresh_projections
from pricing.tests.projections.test_projections import TwoProductCatalog


class RefreshTaskTests(TwoProductCatalog, TestCase):
    """A store's refresh touches that store; all stores by default."""

    def test_refresh_by_store_and_for_all(self) -> None:
        """Two offers of one store, two seeded policies."""
        policies = PricingPolicyRevision.objects.count()
        winners = OfferScenarioProjection.objects.filter(alternative="best")

        written = refresh_projections("store")
        assert winners.count() == len(self.offers) * policies
        assert refresh_projections("elsewhere") == 0
        assert refresh_projections() == written


class PolicyFreezeTests(TestCase):
    """A published policy never changes."""

    def test_a_published_policy_is_frozen(self) -> None:
        """Rules of a published version stay; a new number replaces it."""
        policy = PricingPolicyRevision.objects.create(
            key="trial",
            number=1,
            scenario="cash",
            rules={"allow_codes": False},
        )
        policy.rules = {"allow_codes": True}
        policy.save()
        policy.published_at = timezone.now()
        policy.save()
        policy.rules = {"allow_codes": False}

        raised(policy.save, ValueError)


class PolicyTriggerTests(TestCase):
    """Below the ORM, PostgreSQL refuses to rewrite a published policy."""

    def test_raw_updates_and_deletes_are_refused(self) -> None:
        """Only is_default may move once published."""
        if connection.vendor != "postgresql":
            self.skipTest("Triggers exist on PostgreSQL only.")
        policy = PricingPolicyRevision.objects.get(key="best", number=1)
        PricingPolicyRevision.objects.filter(pk=policy.pk).update(is_default=False)

        raised(
            lambda: PricingPolicyRevision.objects.filter(pk=policy.pk).update(
                rules={"allow_codes": True},
            ),
            Exception,
        )
        raised(
            lambda: PricingPolicyRevision.objects.filter(pk=policy.pk).delete(),
            Exception,
        )
        raised(policy.delete, ValueError)
