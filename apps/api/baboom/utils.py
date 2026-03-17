"""Shared utility types and helpers for the Django project."""

from __future__ import annotations

from typing import TYPE_CHECKING

import strawberry

if TYPE_CHECKING:
    from django.core.exceptions import ValidationError as DjangoValidationError


@strawberry.type
class ValidationError:
    """GraphQL format for validation errors."""

    field: str
    message: str


def format_graphql_errors(e: DjangoValidationError) -> list[ValidationError]:
    """Convert a Django ValidationError into GraphQL validation errors.

    Handles both field-specific errors (error_dict) and non-field errors (error_list).
    """
    errors = []
    if hasattr(e, "error_dict"):
        for field, msgs in e.message_dict.items():
            errors.extend(ValidationError(field=field, message=msg) for msg in msgs)
    elif hasattr(e, "error_list"):
        errors.extend(
            ValidationError(field="non_field_errors", message=msg)
            for msg in e.messages
        )
    else:
        errors.append(ValidationError(field="unknown", message=str(e)))

    return errors
