"""R08: a kept quote reproduces its result from its snapshot, privately."""

from __future__ import annotations

import json
from decimal import Decimal

from django.test import TestCase

from pricing.domain.types import CartLine, Claim, Destination
from pricing.models import PricingPolicyRevision
from pricing.replay import replay
from pricing.services import PricingService, QuoteRequest
from pricing.tests.services.test_pricing_service import _ingest_max_titanium
from promotions.models import ActivationCode, PromotionScope
from promotions.services import PromotionService
from promotions.tests.factories import first_purchase_draft

PERSONAL = "ANA-7Q2"
POSTAL = "01310-100"


class ReplayTests(TestCase):
    """Public code, personal code and destination, replayed without the data."""

    def setUp(self) -> None:
        """Publish two codes and a destination condition on the real offer."""
        self.offer = _ingest_max_titanium()
        seller = self.offer.seller_account
        revision = first_purchase_draft()
        revision.promotion.issuer_seller = seller
        revision.promotion.save()
        PromotionScope.objects.filter(revision=revision).update(ref_id=seller.pk)
        ActivationCode.objects.create(
            revision=revision,
            kind=ActivationCode.Kind.PERSONAL_CODE,
            code=PERSONAL,
        )
        revision.conditions = {
            "root": {
                "all": [
                    {"kind": "code_required"},
                    {
                        "kind": "destination",
                        "country": "BR",
                        "postal_prefixes": ["01"],
                    },
                ],
            },
        }
        revision.save()
        assert PromotionService().publish(revision, "executable").published
        self.policy = PricingPolicyRevision.objects.create(
            key="personal",
            number=1,
            scenario="listed",
            rules={
                "allow_codes": True,
                "allow_private_codes": True,
                "allow_conditions": ["destination"],
            },
        )

    def _quote(self, code: str, postal: str) -> object:
        return PricingService().quote(
            QuoteRequest(
                lines=(CartLine(self.offer.pk),),
                policy=self.policy,
                context={
                    "codes": frozenset({code}),
                    "destination": Destination("BR", postal_code=postal),
                    "claims": (Claim("note", "test", None),),
                },
            ),
        )

    def test_public_and_personal_codes_replay_to_the_same_result(self) -> None:
        """Both codes match after protection; the result is the same."""
        for code in ("PRIMEIRACOMPRA", PERSONAL):
            with self.subTest(code):
                quote = self._quote(code, POSTAL)
                replayed = replay(quote)
                assert quote.merchandise_total == Decimal("79.20")
                assert replayed.merchandise_total == quote.merchandise_total
                assert replayed.applied_revisions == tuple(
                    quote.snapshot["result"]["applied_revisions"],
                )

    def test_a_destination_outside_replays_as_outside(self) -> None:
        """A postal code outside the prefix stays outside after protection."""
        quote = self._quote("PRIMEIRACOMPRA", "20000-000")

        assert quote.merchandise_total == Decimal("99.00")
        assert replay(quote).merchandise_total == Decimal("99.00")

    def test_the_snapshot_keeps_no_private_value(self) -> None:
        """Neither the personal code nor the postal code is stored in clear."""
        text = json.dumps(self._quote(PERSONAL, POSTAL).snapshot)

        assert PERSONAL not in text
        assert POSTAL not in text
        assert "01310" not in text

    def test_replay_reads_no_current_rule(self) -> None:
        """Archiving the promotion later does not change the replay."""
        quote = self._quote("PRIMEIRACOMPRA", POSTAL)
        PromotionService.set_status(
            quote.revisions.get(),
            "archived",
        )

        assert replay(quote).merchandise_total == Decimal("79.20")

    def test_both_fingerprints_are_kept(self) -> None:
        """The original input fingerprint and the protected one."""
        quote = self._quote("PRIMEIRACOMPRA", POSTAL)

        assert quote.input_fingerprint
        assert quote.snapshot["protected_fingerprint"] != quote.input_fingerprint
