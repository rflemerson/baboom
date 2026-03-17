import strawberry
from django.core.exceptions import ValidationError as DjangoValidationError


@strawberry.type
class ValidationError:
    """GraphQL format for validation errors."""

    field: str
    message: str


def format_graphql_errors(e: DjangoValidationError) -> list[ValidationError]:
    """Converts a Django ValidationError into a list of strawberry ValidationErrors.

    Handles both field-specific errors (error_dict) and non-field errors (error_list).
    """
    errors = []
    if hasattr(e, "error_dict"):
        for field, msgs in e.message_dict.items():
            for msg in msgs:
                errors.append(ValidationError(field=field, message=msg))
    elif hasattr(e, "error_list"):
        for msg in e.messages:
            errors.append(ValidationError(field="non_field_errors", message=msg))
    else:
        errors.append(ValidationError(field="unknown", message=str(e)))

    return errors
