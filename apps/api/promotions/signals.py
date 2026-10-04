"""Signals promotions send; listeners live in the apps that depend on them."""

from django.dispatch import Signal

# Sent after a revision was published or changed status. ``revision_id`` names
# it; every offer it may reach has to be priced again.
revision_changed = Signal()
