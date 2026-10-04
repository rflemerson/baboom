"""One traversal of normalized condition trees, independent of frameworks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def leaves(node: object) -> Iterator[dict]:
    """Yield leaves in document order from all/any/not trees."""
    if not isinstance(node, dict):
        return
    for combinator in ("all", "any"):
        if combinator in node:
            for child in node[combinator]:
                yield from leaves(child)
            return
    if "not" in node:
        yield from leaves(node["not"])
    else:
        yield node
