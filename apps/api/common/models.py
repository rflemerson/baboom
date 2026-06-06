"""Shared abstract base models for the project."""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    """Abstract base model with creation and update timestamps."""

    created_at = models.DateTimeField(
        _("Created At"),
        db_index=True,
        default=timezone.now,
        editable=False,
    )
    updated_at = models.DateTimeField(
        _("Updated At"),
        auto_now=True,
    )

    class Meta:
        """Meta options."""

        abstract = True
