"""The refresh task and the frozen policies it reads."""

from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from common.testing import raised
from pricing.models import PricingPolicyRevision
from pricing.tasks import refresh_projections
from pricing.tests.projections.test_projections import TwoProductCatalog


class RefreshTaskTests(TwoProductCatalog, TestCase):
    """A store's refresh touches that store; all stores by default."""

    def test_refresh_by_store_and_for_all(self) -> None:
        """Two offers of one store, two seeded policies."""
        policies = PricingPolicyRevision.objects.count()

        assert refresh_projections("store") == len(self.offers) * policies
        assert refresh_projections("elsewhere") == 0
        assert refresh_projections() == len(self.offers) * policies


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
