"""Assertions shared by the test suites of every app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from collections.abc import Callable


def raised[E: Exception](operation: Callable[[], object], expected: type[E]) -> E:
    """Return the exception an operation is expected to raise.

    The operation runs in its own savepoint, so a refused write leaves the
    test's transaction usable.
    """
    try:
        with transaction.atomic():
            operation()
    except expected as error:
        return error
    message = f"Expected {expected.__name__} to be raised."
    raise AssertionError(message)
