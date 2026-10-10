"""The refresh task and the frozen policies it reads."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from common.testing import raised
from pricing.models import OfferScenarioProjection, PricingPolicyRevision
from pricing.policies import PolicyService
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

    def test_seeded_policies_are_valid(self) -> None:
        """The seeds pass the same check."""
        for policy in PricingPolicyRevision.objects.all():
            policy.clean()
