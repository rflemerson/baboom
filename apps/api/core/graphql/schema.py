"""Composable exports for the core GraphQL schema."""

from .mutations import CoreMutation
from .queries import CoreQuery

__all__ = ["CoreMutation", "CoreQuery"]
