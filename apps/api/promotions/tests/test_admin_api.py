"""The admin JSON API (the MCP surface) publishes through the same service."""

from __future__ import annotations

import json
from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase

from promotions.models import PromotionRevision
from promotions.tests.factories import first_purchase_draft


class AdminApiPublishTests(TestCase):
    """A curator or an agent publishes by setting the status field."""

    URL = "/admin-api/api/v1/promotions/promotionrevision/{}/"

    def setUp(self) -> None:
        """Log in a curator and build a complete draft."""
        user = get_user_model().objects.create(
            username="curator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        self.revision = first_purchase_draft()

    def _patch(self, data: dict[str, object]) -> tuple[int, dict]:
        response = self.client.patch(
            self.URL.format(self.revision.pk),
            data=json.dumps(data),
            content_type="application/json",
        )
        return response.status_code, json.loads(response.content or b"{}")

    def test_setting_executable_publishes_and_freezes(self) -> None:
        """The status field is the whole publication workflow."""
        status, body = self._patch({"status": "executable"})

        self.revision.refresh_from_db()
        assert status < HTTPStatus.BAD_REQUEST, body
        assert self.revision.status == PromotionRevision.Status.EXECUTABLE
        assert self.revision.content_hash

    def test_an_invalid_publication_is_refused_with_its_reason(self) -> None:
        """No evidence: the client is told why, and the draft stays a draft."""
        self.revision.evidence.clear()

        status, body = self._patch({"status": "executable"})

        self.revision.refresh_from_db()
        assert status == HTTPStatus.BAD_REQUEST
        assert "evidence" in json.dumps(body)
        assert self.revision.status == PromotionRevision.Status.DRAFT

    def test_published_terms_do_not_change_through_the_api(self) -> None:
        """Only the status of a published revision is writable."""
        self._patch({"status": "executable"})

        self._patch({"limitations": "rewritten by an agent"})

        self.revision.refresh_from_db()
        assert self.revision.limitations != "rewritten by an agent"

    def test_suspending_keeps_the_terms(self) -> None:
        """Suspension is a status move."""
        self._patch({"status": "executable"})
        before = PromotionRevision.objects.get(pk=self.revision.pk).content_hash

        status, body = self._patch({"status": "suspended"})

        self.revision.refresh_from_db()
        assert status < HTTPStatus.BAD_REQUEST, body
        assert self.revision.status == PromotionRevision.Status.SUSPENDED
        assert self.revision.content_hash == before
