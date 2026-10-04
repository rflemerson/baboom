"""Signals the catalog sends; listeners live in the apps that depend on core."""

from django.dispatch import Signal

# Sent after treebeard moved a category and its descendants. A move rewrites
# paths with raw SQL and never calls ``save()``. ``category_id`` names the
# node moved: every offer below it may now sit under other ancestors.
category_moved = Signal()
