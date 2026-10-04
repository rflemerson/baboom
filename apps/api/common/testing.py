"""Assertions shared by the test suites of every app."""

from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING

from django.db import connection, transaction

if TYPE_CHECKING:
    from collections.abc import Callable


def raised[E: Exception](operation: Callable[[], object], expected: type[E]) -> E:
    """Return the exception an operation is expected to raise.

    Inside a test's transaction the operation runs in its own savepoint, so a
    refused write leaves the transaction usable; a test without a database
    runs it as is.
    """
    guard = transaction.atomic() if connection.in_atomic_block else nullcontext()
    try:
        with guard:
            operation()
    except expected as error:
        return error
    message = f"Expected {expected.__name__} to be raised."
    raise AssertionError(message)
