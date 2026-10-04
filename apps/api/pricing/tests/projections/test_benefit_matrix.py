"""SYNTHETIC: every policy against every coupon and cashback filter."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from pricing.models import PricingPolicyRevision
from pricing.projections import ProjectionService
from pricing.selectors import BenefitFilter
from pricing.tests.projections.test_benefit_alternatives import BenefitCatalog

REQUIRED, FORBIDDEN, ANY = True, False, None
HUNDRED, DEAR = Decimal(100), Decimal(120)

# (coupon, cashback) -> {product: price} under the `best` policy: A (R$ 100)
# earns cashback; B (R$ 120) costs R$ 100 with a coupon.
BEST = {
    (ANY, ANY): {"A": HUNDRED, "B": HUNDRED},
    (ANY, REQUIRED): {"A": HUNDRED},
    (ANY, FORBIDDEN): {"A": HUNDRED, "B": HUNDRED},
    (REQUIRED, ANY): {"B": HUNDRED},
    (REQUIRED, REQUIRED): {},
    (REQUIRED, FORBIDDEN): {"B": HUNDRED},
    (FORBIDDEN, ANY): {"A": HUNDRED, "B": DEAR},
    (FORBIDDEN, REQUIRED): {"A": HUNDRED},
    (FORBIDDEN, FORBIDDEN): {"A": HUNDRED, "B": DEAR},
}

# The normal policy applies no benefit: the store's price uses neither, so a
# filter that requires one finds nothing.
NORMAL = {
    cell: ({} if REQUIRED in cell else {"A": HUNDRED, "B": DEAR}) for cell in BEST
}


class BenefitMatrixTests(BenefitCatalog, TestCase):
    """Required, forbidden and indifferent, for each benefit and each policy."""

    def setUp(self) -> None:
        """Give A R$ 15 back and B a public R$ 20 coupon."""
        super().setUp()
        self._publish(self.offers["A"], "cashback", {}, reward_rate=Decimal(15))
        self._publish(
            self.offers["B"], "fixed_amount", {"amount": "20"}, code="SYNTH20"
        )
        ProjectionService().refresh()

    def _priced(
        self,
        key: str,
        *,
        coupon: bool | None,
        cashback: bool | None,
    ) -> dict:
        policy = PricingPolicyRevision.objects.get(key=key)
        ranking = self._ranking(policy, BenefitFilter(coupon, cashback))
        return {name: price for name, price in ranking if price is not None}

    def test_the_best_policy(self) -> None:
        """Each cell reads the cheapest alternative with exactly those benefits."""
        for (coupon, cashback), expected in BEST.items():
            with self.subTest(coupon=coupon, cashback=cashback):
                assert (
                    self._priced("best", coupon=coupon, cashback=cashback) == expected
                )

    def test_the_normal_policy(self) -> None:
        """The store's price answers every filter that does not require a benefit."""
        for (coupon, cashback), expected in NORMAL.items():
            with self.subTest(coupon=coupon, cashback=cashback):
                assert (
                    self._priced("normal", coupon=coupon, cashback=cashback) == expected
                )
