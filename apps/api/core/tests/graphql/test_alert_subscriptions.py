import json

from django.test import RequestFactory, TestCase
from strawberry.django.views import GraphQLView

from baboom.schema import schema
from core.models import APIKey, AlertSubscriber


class GraphQLAlertSubscriptionTests(TestCase):
    """Tests for the alert subscription mutation."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()
        self.api_key_obj = APIKey.objects.create(name="Test Client")
        self.valid_key = self.api_key_obj.key
        self.view = GraphQLView.as_view(schema=schema)

    def _execute_mutation(self, email: str):
        mutation = """
        mutation SubscribeAlerts($email: String!) {
          subscribeAlerts(email: $email) {
            success
            alreadySubscribed
            email
            errors {
              field
              message
            }
          }
        }
        """
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": mutation, "variables": {"email": email}}),
            content_type="application/json",
            HTTP_X_API_KEY=self.valid_key,
        )
        response = self.view(request)
        return json.loads(response.content)

    def test_subscribe_alerts_creates_new_subscriber(self):
        """Test that a new email subscription succeeds."""
        result = self._execute_mutation("new-subscriber@example.com")

        self.assertTrue(result["data"]["subscribeAlerts"]["success"])
        self.assertFalse(result["data"]["subscribeAlerts"]["alreadySubscribed"])
        self.assertEqual(
            result["data"]["subscribeAlerts"]["email"], "new-subscriber@example.com"
        )

    def test_subscribe_alerts_returns_duplicate_state(self):
        """Test that duplicate subscriptions are handled explicitly."""
        subscriber = AlertSubscriber.objects.create(email="duplicate@example.com")

        result = self._execute_mutation(subscriber.email)

        self.assertFalse(result["data"]["subscribeAlerts"]["success"])
        self.assertTrue(result["data"]["subscribeAlerts"]["alreadySubscribed"])
        self.assertEqual(result["data"]["subscribeAlerts"]["email"], subscriber.email)

    def test_subscribe_alerts_returns_validation_errors(self):
        """Test that invalid emails return formatted validation errors."""
        result = self._execute_mutation("not-an-email")

        self.assertFalse(result["data"]["subscribeAlerts"]["success"])
        self.assertEqual(result["data"]["subscribeAlerts"]["email"], "not-an-email")
        self.assertEqual(
            result["data"]["subscribeAlerts"]["errors"][0]["field"], "email"
        )
