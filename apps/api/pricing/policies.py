"""Publish pricing policies: validate, freeze, project.

A published policy is frozen, so ``PricingPolicyRevision.clean`` checks its
rules first; this workflow is the one place a policy becomes public.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .invalidation import Repricing

if TYPE_CHECKING:
    from .models import PricingPolicyRevision


class PolicyService:
    """Publish a policy once its rules are valid, and project it."""

    @transaction.atomic
    def publish(self, policy: PricingPolicyRevision) -> None:
        """Validate, freeze and project a policy for every linked offer."""
        if policy.published_at is not None:
            msg = "The policy is already published."
            raise ValidationError(msg)
        policy.full_clean()
        policy.published_at = timezone.now()
        policy.save()
        Repricing().offers(None)
