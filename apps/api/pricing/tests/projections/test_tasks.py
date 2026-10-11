"""The refresh task and the frozen policies it reads."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from common.testing import raised
from pricing.models import (
    OfferScenarioProjection,
    PricingPolicyRevision,
    ProjectionRefreshRequest,
)
from pricing.policies import PolicyService
from pricing.projections import ProjectionService
from pricing.selectors import public_policy
from pricing.tasks import drain_projection_requests, refresh_projections
from pricing.tests.projections.test_projections import TwoProductCatalog


class RefreshTaskTests(TwoProductCatalog, TestCase):
    """A store's refresh touches that store; all stores by default."""

    def test_refresh_by_store_and_for_all(self) -> None:
        """Two offers of one store, two seeded policies."""
        policies = len(ProjectionService.policies())
        winners = OfferScenarioProjection.objects.filter(alternative="best")

        written = refresh_projections("store")
        assert winners.count() == len(self.offers) * policies
        assert refresh_projections("elsewhere") == 0
        assert refresh_projections() == written


class DrainTaskTests(TwoProductCatalog, TestCase):
    """The worker reprices what changes queued, once, and empties the queue."""

    def test_queued_offers_are_merged_into_one_refresh(self) -> None:
        """A twice and B once: one refresh of both, no request left."""
        a, b = self.offers["A"].pk, self.offers["B"].pk
        for ids in ([a], [a, b], [a]):
            ProjectionRefreshRequest.objects.create(offer_ids=ids)
        winners = OfferScenarioProjection.objects.filter(alternative="best")

        written = drain_projection_requests()

        assert written == refresh_projections()
        assert winners.count() == len(self.offers) * len(ProjectionService.policies())
        assert not ProjectionRefreshRequest.objects.exists()
        assert drain_projection_requests() == 0

    def test_a_request_for_every_offer_refreshes_all(self) -> None:
        """One request without ids widens the whole batch."""
        ProjectionRefreshRequest.objects.create(offer_ids=[self.offers["A"].pk])
        ProjectionRefreshRequest.objects.create(offer_ids=None)

        assert drain_projection_requests() == refresh_projections()


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
        policy = public_policy("best")
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


class PolicyValidationTests(TestCase):
    """A policy is checked before it is frozen."""

    def test_wrong_rules_are_refused_before_publishing(self) -> None:
        """An unknown key, a string flag and an unknown objective."""
        policy = PricingPolicyRevision.objects.create(
            key="broken",
            number=1,
            scenario="best",
            rules={"allow_code": True, "allow_rewards": "yes", "objective": "cheap"},
        )

        error = raised(lambda: PolicyService().publish(policy), ValidationError)

        text = str(error)
        assert "unknown rule 'allow_code'" in text
        assert "allow_rewards must be true or false" in text
        assert "objective must be one of" in text
        policy.refresh_from_db()
        assert policy.published_at is None

    def test_policies_in_force_are_valid(self) -> None:
        """The newest version of each public policy passes the same check."""
        for policy in ProjectionService.policies():
            policy.clean()
