"""SYNTHETIC: policy rules of any JSON type are refused, never a crash."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from common.testing import raised
from pricing.models import RULES, PricingPolicyRevision

JSON_VALUES = (([], "list"), ({}, "object"), (None, "null"), (5, "number"))
JSON_VALUES += ((True, "boolean"), ("unknown", "unknown string"))

# What each rule accepts among the values above.
ACCEPTED = {
    "objective": [],
    "apply_benefits": [True],
    "accepted_semantics": [[]],
    "accepted_evidence": [[]],
    "cash_methods": [[]],
    "include_unknown_payment": [True],
    "allow_codes": [True],
    "auto_public_codes": [True],
    "allow_private_codes": [True],
    "allow_rewards": [True],
    "allow_conditions": [[]],
    "net_cost_counts_money_rewards": [True],
    "assume_full_caps": [True],
    "max_combinations": [5],
    "freshness_hours": [5],
}


class PolicyRulesTests(SimpleTestCase):
    """Every rule meets every JSON type and answers with a validation error."""

    def test_every_rule_covers_each_json_type(self) -> None:
        """Nothing but ValidationError escapes ``clean``; valid values pass."""
        assert set(ACCEPTED) == set(RULES)
        for key in RULES:
            for value, label in JSON_VALUES:
                with self.subTest(rule=key, value=label):
                    policy = PricingPolicyRevision(
                        key="synthetic", number=1, scenario="best", rules={key: value}
                    )
                    if any(
                        value == ok and type(value) is type(ok) for ok in ACCEPTED[key]
                    ):
                        policy.clean()
                    else:
                        raised(policy.clean, ValidationError)

    def test_rules_that_are_not_an_object_are_refused(self) -> None:
        """A list or a scalar in place of the rules is a validation error."""
        for value in ([], [1], None, 5, "rules"):
            with self.subTest(rules=value):
                policy = PricingPolicyRevision(
                    key="synthetic", number=1, scenario="best", rules=value
                )
                raised(policy.clean, ValidationError)
