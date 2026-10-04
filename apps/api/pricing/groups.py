"""Name checkout groups and private values without keeping them in clear."""

from __future__ import annotations

import hashlib
import hmac
from typing import TYPE_CHECKING

from django.conf import settings

from .domain.types import CheckoutGroup

if TYPE_CHECKING:
    from .domain.types import CartLine, Destination


def token(value: str) -> str:
    """Return a keyed token for a private value: equal values, equal tokens."""
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"token:{digest}"


def group_fingerprint(
    lines: tuple[CartLine, ...],
    destination: Destination | None,
) -> str:
    """Name a checkout group by its lines and destination, never in clear.

    Shipping depends on what is shipped and where: quantity and offers are
    part of the key, the postal code only as a keyed token.
    """
    parts = sorted(f"{line.offer_id}x{line.quantity}" for line in lines)
    place = ""
    if destination is not None:
        place = "|".join(
            (
                destination.country,
                destination.subdivision,
                token(destination.postal_code) if destination.postal_code else "",
            ),
        )
    text = ";".join(parts) + "@" + place
    return hashlib.sha256(text.encode()).hexdigest()


def one_group(
    lines: tuple[CartLine, ...],
    destination: Destination | None,
) -> tuple[CheckoutGroup, ...]:
    """Return the single checkout group of a cart that names none."""
    return (
        CheckoutGroup(
            group_fingerprint(lines, destination),
            frozenset(line.offer_id for line in lines),
        ),
    )
