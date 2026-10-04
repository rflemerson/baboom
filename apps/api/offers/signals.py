"""Signals offers send; listeners live in the apps that depend on offers."""

from django.dispatch import Signal

# Sent after a store's crawl committed new readings. ``store_slug`` names the
# store whose offers may have changed price, stock or listing.
offers_observed = Signal()
