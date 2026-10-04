"""Every reason a revision cannot be published, and the admin paths around it."""

from __future__ import annotations

from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase

from common.testing import raised
from promotions.models import (
    ActivationCode,
    Promotion,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
    RewardTerms,
)
from promotions.services import PromotionService
from promotions.tests.factories import first_purchase_draft


class ValidationTests(TestCase):
    """Each check names its reason."""

    def setUp(self) -> None:
        """Build a complete draft to break one way at a time."""
        self.revision = first_purchase_draft()
        self.service = PromotionService()

    def _errors(self, status: str = "informative") -> str:
        return " ".join(self.service.validate(self.revision, status))

    def _conditions(self, leaf: dict) -> str:
        self.revision.conditions = {"root": leaf}
        self.revision.save()
        return self._errors()

    def test_missing_ids_in_every_kind_of_leaf(self) -> None:
        """Channels, markets, programmes and issuers are checked like keys."""
        for leaf in (
            {"kind": "channel", "channel_ids": [999]},
            {"kind": "market", "market_ids": [999]},
            {"kind": "program_member", "program_id": 999},
            {"kind": "new_customer", "issuer": "program", "issuer_id": 999},
        ):
            with self.subTest(leaf["kind"]):
                assert "missing" in self._conditions(leaf)

    def test_effect_stage_and_target_rules(self) -> None:
        """Rewards at the reward stage only; shipping discounts target shipping."""
        PromotionEffect.objects.filter(revision=self.revision).update(stage="reward")
        PromotionEffect.objects.create(
            revision=self.revision,
            position=2,
            kind="cashback",
            stage="order",
            basis="eligible_subtotal",
            target="order",
            allocation="once",
        )
        PromotionEffect.objects.create(
            revision=self.revision,
            position=3,
            kind="shipping_discount",
            stage="shipping",
            basis="component",
            target="order",
            allocation="once",
            parameters={"free": True},
        )

        errors = self._errors()

        assert "only rewards use the reward stage" in errors
        assert "a reward applies at the reward stage" in errors
        assert "targets shipping" in errors

    def test_ordering_problems(self) -> None:
        """A malformed edge, or one naming a missing effect."""
        self.revision.ordering = [{"before": "x"}]
        self.revision.save()
        assert "Precedence" in self._errors()

        self.revision.ordering = [{"before": 1, "after": 9}]
        self.revision.save()
        assert "do not exist" in self._errors()

    def test_duplicate_codes_and_missing_scope_rows(self) -> None:
        """One code once; a scope names a row that exists."""
        ActivationCode.objects.create(
            revision=self.revision,
            kind="public_code",
            code="PRIMEIRACOMPRA",
        )
        PromotionScope.objects.create(
            revision=self.revision,
            role="target",
            kind="product",
            ref_id=999_999,
        )

        errors = self._errors()

        assert "appears twice" in errors
        assert "no product #999999" in errors

    def test_executable_needs_effects_and_a_target(self) -> None:
        """Nothing to grant, or no target, is informative at most."""
        PromotionEffect.objects.filter(revision=self.revision).delete()
        PromotionScope.objects.filter(revision=self.revision).delete()

        errors = self._errors("executable")

        assert "at least one effect" in errors
        assert "names what it targets" in errors


class PublishStateTests(TestCase):
    """Publication, status moves and revisions refuse impossible states."""

    def test_impossible_moves(self) -> None:
        """Publish as draft, publish twice, move to draft, revise nothing."""
        revision = first_purchase_draft()
        service = PromotionService()

        assert not service.publish(revision, "draft").published
        assert service.publish(revision, "executable").published
        assert not service.publish(revision, "executable").published
        raised(lambda: service.set_status(revision, "draft"), ValueError)
        empty = Promotion.objects.create(
            title="Empty",
            issuer_seller=revision.promotion.issuer_seller,
            source_key="empty",
        )
        raised(lambda: service.revise(empty), ValueError)

    def test_a_draft_moves_only_through_the_service(self) -> None:
        """Suspending a draft is refused."""
        draft = first_purchase_draft()

        raised(lambda: PromotionService.set_status(draft, "suspended"), ValueError)


class AdminTests(TestCase):
    """The HTML admin offers the same workflow."""

    def setUp(self) -> None:
        """Log in a curator."""
        user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)

    def test_start_revision_action(self) -> None:
        """The action copies the latest revision into a new draft."""
        revision = first_purchase_draft()
        assert PromotionService().publish(revision, "executable").published

        self.client.post(
            "/admin/promotions/promotion/",
            {"action": "start_revision", "_selected_action": [revision.promotion_id]},
        )
        empty = Promotion.objects.create(
            title="Empty",
            issuer_seller=revision.promotion.issuer_seller,
            source_key="empty",
        )
        self.client.post(
            "/admin/promotions/promotion/",
            {"action": "start_revision", "_selected_action": [empty.pk]},
        )

        drafts = PromotionRevision.objects.filter(status="draft")
        assert list(drafts.values_list("number", flat=True)) == [2]

    def test_a_published_revision_shows_its_terms_read_only(self) -> None:
        """Only the status is editable in the change form."""
        revision = first_purchase_draft()
        assert PromotionService().publish(revision, "executable").published

        page = self.client.get(
            f"/admin/promotions/promotionrevision/{revision.pk}/change/"
        )

        assert page.status_code == HTTPStatus.OK
        assert 'name="limitations"' not in page.content.decode()
        assert 'name="status"' in page.content.decode()

    def test_reward_terms_of_a_published_revision_are_read_only(self) -> None:
        """Change and delete are refused once published."""
        revision = first_purchase_draft()
        cashback = PromotionEffect.objects.create(
            revision=revision,
            position=2,
            kind="cashback",
            stage="reward",
            basis="eligible_subtotal",
            target="order",
            allocation="once",
        )
        terms = RewardTerms.objects.create(effect=cashback, credited_as="money", rate=5)
        assert PromotionService().publish(revision, "informative").published

        page = self.client.post(
            f"/admin/promotions/rewardterms/{terms.pk}/delete/",
            {"post": "yes"},
        )

        assert page.status_code == HTTPStatus.FORBIDDEN
        assert RewardTerms.objects.filter(pk=terms.pk).exists()
