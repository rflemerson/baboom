"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

import json

from django.test import TestCase

from core.models import (
    AlertSubscriber,
)


class PublicAlertSubscriptionRESTTests(TestCase):
    """Tests for the public alert subscription REST endpoint."""

    def _execute_subscription(
        self,
        email: str,
    ) -> dict[str, object]:
        """Execute the alert subscription REST endpoint and decode the JSON response."""
        response = self.client.post(
            "/api/alerts/subscribe/",
            data=json.dumps({"email": email}),
            content_type="application/json",
        )
        return json.loads(response.content)

    def test_subscribe_alerts_creates_new_subscriber(self) -> None:
        """A new public email subscription should succeed through REST."""
        result = self._execute_subscription("new-subscriber@example.com")

        assert result["success"]
        assert not result["alreadySubscribed"]
        assert result["email"] == "new-subscriber@example.com"

    def test_subscribe_alerts_returns_duplicate_state(self) -> None:
        """Duplicate subscriptions should be reported explicitly."""
        subscriber = AlertSubscriber.objects.create(email="duplicate@example.com")

        result = self._execute_subscription(subscriber.email)

        assert not result["success"]
        assert result["alreadySubscribed"]
        assert result["email"] == subscriber.email

    def test_subscribe_alerts_returns_validation_errors(self) -> None:
        """Invalid emails should return formatted validation errors."""
        result = self._execute_subscription("not-an-email")

        assert not result["success"]
        assert result["email"] == "not-an-email"
        assert result["errors"][0]["field"] == "email"
