"""The typed documents refuse terms that cannot be computed."""

from __future__ import annotations

from django.test import SimpleTestCase
from pydantic import ValidationError

from common.testing import raised
from promotions.schemas import (
    MAX_DEPTH,
    MAX_NODES,
    ConditionTree,
    MultibuyParams,
    PointsParams,
    ShippingDiscountParams,
    TieredParams,
    leaves,
)

CODE = {"kind": "code_required"}


def _nested(depth: int) -> dict:
    node: dict = CODE
    for _ in range(depth):
        node = {"not": node}
    return node


class TreeTests(SimpleTestCase):
    """Depth and size are capped; leaves are found in order."""

    def test_caps(self) -> None:
        """Too deep or too large is refused."""
        raised(
            lambda: ConditionTree.model_validate({"root": _nested(MAX_DEPTH)}),
            ValidationError,
        )
        raised(
            lambda: ConditionTree.model_validate(
                {"root": {"any": [CODE] * MAX_NODES}},
            ),
            ValidationError,
        )

    def test_leaves(self) -> None:
        """Every leaf under all, any and not."""
        tree = ConditionTree.model_validate(
            {"root": {"all": [CODE, {"any": [{"not": CODE}]}]}},
        )

        assert [leaf.kind for leaf in leaves(tree.root)] == ["code_required"] * 2
        assert leaves(None) == []


class EffectParamTests(SimpleTestCase):
    """One form per effect, and sensible numbers."""

    def test_refusals(self) -> None:
        """Each invalid form raises."""
        for build in (
            lambda: ShippingDiscountParams(free=True, rate="10"),
            ShippingDiscountParams,
            PointsParams,
            lambda: PointsParams(per_currency_unit="1", points=5),
            lambda: MultibuyParams(buy=2, pay=2),
            lambda: TieredParams(tiers=[{"min_quantity": 2}]),
            lambda: TieredParams(
                tiers=[
                    {"min_quantity": 3, "rate": "5"},
                    {"min_quantity": 2, "rate": "10"},
                ],
            ),
        ):
            raised(build, ValidationError)
