"""Revisions publish only valid terms and never change once published."""

from __future__ import annotations

from django.db import IntegrityError, connection
from django.test import TestCase

from common.testing import raised
from promotions.models import (
    ActivationCode,
    CompatibilityRule,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
    PublishedRevisionError,
)
from promotions.services import PromotionService
from promotions.tests.factories import first_purchase_draft


class PublishTests(TestCase):
    """Publishing validates, hashes and freezes."""

    def setUp(self) -> None:
        """Build a complete draft of a real promotion."""
        self.revision = first_purchase_draft()
        self.service = PromotionService()

    def test_a_complete_draft_publishes_as_executable(self) -> None:
        """PRIMEIRACOMPRA has a target, an effect, conditions and evidence."""
        result = self.service.publish(self.revision, "executable")

        assert result.published, result.errors
        assert self.revision.status == "executable"
        assert self.revision.published_at is not None
        assert self.revision.content_hash == PromotionService.content_hash(
            self.revision
        )

    def test_a_revision_without_evidence_is_only_informative(self) -> None:
        """No evidence: it can be recorded, never computed."""
        self.revision.evidence.clear()

        executable = self.service.publish(self.revision, "executable")
        informative = self.service.publish(self.revision, "informative")

        assert not executable.published
        assert "rests on evidence" in " ".join(executable.errors)
        assert informative.published

    def test_unknown_condition_kinds_are_refused(self) -> None:
        """A tree is data over a closed set of leaves."""
        self.revision.conditions = {"root": {"kind": "python", "code": "1"}}
        self.revision.save()

        result = self.service.publish(self.revision, "informative")

        assert not result.published
        assert result.errors[0].startswith("Conditions")

    def test_a_condition_naming_a_missing_row_is_refused(self) -> None:
        """Ids in leaves are checked like foreign keys."""
        self.revision.conditions = {
            "root": {"kind": "seller", "seller_account_ids": [999_999]},
        }
        self.revision.save()

        result = self.service.publish(self.revision, "informative")

        assert "missing seller ids [999999]" in result.errors[0]

    def test_a_minimum_in_another_currency_is_refused(self) -> None:
        """Every amount is in the revision's currency."""
        self.revision.conditions = {
            "root": {
                "kind": "min_amount",
                "amount": "50",
                "currency": "USD",
                "basis": "before_discounts",
                "scope": "order",
            },
        }
        self.revision.save()

        assert not self.service.publish(self.revision, "informative").published

    def test_effect_parameters_are_typed_per_kind(self) -> None:
        """A percentage above 100 is not a percentage."""
        PromotionEffect.objects.filter(revision=self.revision).update(
            parameters={"rate": "120"},
        )

        result = self.service.publish(self.revision, "informative")

        assert not result.published
        assert "Effect" in result.errors[0]

    def test_a_precedence_cycle_is_refused(self) -> None:
        """Two effects each computed before the other."""
        PromotionEffect.objects.create(
            revision=self.revision,
            position=2,
            kind="fixed_amount",
            stage="order",
            basis="current",
            target="order",
            allocation="prorated",
            parameters={"amount": "10"},
        )
        self.revision.ordering = [
            {"before": 1, "after": 2},
            {"before": 2, "after": 1},
        ]
        self.revision.save()

        result = self.service.publish(self.revision, "informative")

        assert "cycle" in " ".join(result.errors)

    def test_cashback_needs_its_rate_to_be_executable(self) -> None:
        """A reward with no terms is informative at most."""
        PromotionEffect.objects.create(
            revision=self.revision,
            position=2,
            kind="cashback",
            stage="reward",
            basis="eligible_subtotal",
            target="order",
            allocation="once",
        )

        result = self.service.publish(self.revision, "executable")

        assert "reward terms" in " ".join(result.errors)

    def test_contradicting_compatibility_blocks_publication(self) -> None:
        """A says it combines with B while B, published, says it does not."""
        other = first_purchase_draft()
        CompatibilityRule.objects.create(
            revision=other,
            other_kind="promotion",
            other_ref=str(self.revision.promotion_id),
            verdict="forbidden",
        )
        assert self.service.publish(other, "informative").published
        CompatibilityRule.objects.create(
            revision=self.revision,
            other_kind="promotion",
            other_ref=str(other.promotion_id),
            verdict="allowed",
        )

        result = self.service.publish(self.revision, "informative")

        assert "says the opposite" in " ".join(result.errors)


class FrozenTests(TestCase):
    """A published revision and everything it owns are immutable."""

    def setUp(self) -> None:
        """Publish the real promotion."""
        self.revision = first_purchase_draft()
        assert PromotionService().publish(self.revision, "executable").published

    def test_terms_cannot_change(self) -> None:
        """Editing a published revision raises."""
        self.revision.limitations = "changed"

        raised(self.revision.save, PublishedRevisionError)

    def test_owned_rows_cannot_change_be_added_or_removed(self) -> None:
        """Codes, scopes and effects are frozen with it."""
        code = ActivationCode.objects.get(revision=self.revision)
        code.code = "OTHER"

        raised(code.save, PublishedRevisionError)
        raised(
            lambda: PromotionScope.objects.create(
                revision=self.revision,
                role="target",
                mode="exclude",
                kind="external_category",
                external_ref="Kits",
            ),
            PublishedRevisionError,
        )
        raised(
            PromotionEffect.objects.get(revision=self.revision).delete,
            PublishedRevisionError,
        )

    def test_status_moves_among_published_states(self) -> None:
        """Suspend and archive only change status."""
        before = PromotionService.content_hash(self.revision)

        PromotionService.set_status(self.revision, "suspended")

        assert self.revision.status == "suspended"
        assert PromotionService.content_hash(self.revision) == before
        raised(
            lambda: PromotionService.set_status(self.revision, "draft"),
            ValueError,
        )

    def test_a_published_revision_is_archived_not_deleted(self) -> None:
        """History keeps every published revision."""
        raised(self.revision.delete, PublishedRevisionError)

    def test_revise_copies_into_an_editable_draft(self) -> None:
        """An edit is a new revision; the old one keeps its hash."""
        old_hash = self.revision.content_hash

        draft = PromotionService().revise(self.revision.promotion)
        draft.limitations = "Now known to stack with Pix."
        draft.save()
        assert PromotionService().publish(draft, "executable").published

        self.revision.refresh_from_db()
        assert draft.number == self.revision.number + 1
        assert self.revision.content_hash == old_hash
        assert draft.content_hash != old_hash

    def test_the_database_refuses_raw_updates_on_postgresql(self) -> None:
        """Below the ORM, the trigger freezes the terms too."""
        if connection.vendor != "postgresql":
            self.skipTest("Triggers exist on PostgreSQL only.")
        raised(
            lambda: PromotionRevision.objects.filter(pk=self.revision.pk).update(
                limitations="raw",
            ),
            Exception,
        )
        raised(
            lambda: ActivationCode.objects.filter(revision=self.revision).update(
                code="RAW",
            ),
            Exception,
        )

    def test_saving_as_published_outside_the_service_is_refused(self) -> None:
        """A draft cannot skip validation by setting its status."""
        draft = first_purchase_draft()
        draft.status = "executable"

        raised(draft.save, PublishedRevisionError)
        raised(
            lambda: PromotionRevision.objects.filter(pk=draft.pk).update(
                status="executable",
            ),
            IntegrityError,
        )
