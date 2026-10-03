"""Build a real promotion from the audit's evidence."""

from __future__ import annotations

from datetime import UTC, datetime

from commerce.models import Currency
from commerce.tests.factories import SellerAccountFactory
from offers.models import Evidence
from promotions.models import (
    ActivationCode,
    Promotion,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
)

VERIFIED = datetime(2026, 10, 3, 17, 25, tzinfo=UTC)


def first_purchase_conditions(seller_id: int) -> dict[str, object]:
    """Return the terms: new to the store, with the code, above R$ 249."""
    return {
        "root": {
            "all": [
                {"kind": "code_required"},
                {"kind": "new_customer", "issuer": "seller", "issuer_id": seller_id},
                {
                    "kind": "min_amount",
                    "amount": "249",
                    "currency": "BRL",
                    "basis": "before_discounts",
                    "scope": "order",
                },
            ],
        },
    }


def first_purchase_draft() -> PromotionRevision:
    """Integralmédica PRIMEIRACOMPRA: 20% on a first order above R$ 249."""
    seller = SellerAccountFactory(is_channel_owner=True, external_id="")
    promotion = Promotion.objects.create(
        title="Primeira compra 20%",
        issuer_seller=seller,
        source_key="central-promocoes/primeira-compra",
    )
    revision = PromotionRevision.objects.create(
        promotion=promotion,
        number=1,
        currency=Currency.objects.get(code="BRL"),
        timezone="America/Sao_Paulo",
        verified_at=VERIFIED,
        conditions=first_purchase_conditions(seller.pk),
        limitations="End date unknown; stacking with Pix unknown.",
    )
    revision.evidence.add(
        Evidence.objects.create(
            kind=Evidence.Kind.ANNOUNCEMENT,
            source_url="https://www.integralmedica.com.br/central-promocoes",
            excerpt="20%OFF Utilizando o cupom PRIMEIRACOMPRA",
        ),
    )
    ActivationCode.objects.create(
        revision=revision,
        kind=ActivationCode.Kind.PUBLIC_CODE,
        code="PRIMEIRACOMPRA",
    )
    PromotionScope.objects.create(
        revision=revision,
        role=PromotionScope.Role.TARGET,
        kind=PromotionScope.Kind.SELLER_ACCOUNT,
        ref_id=seller.pk,
    )
    PromotionEffect.objects.create(
        revision=revision,
        position=1,
        kind=PromotionEffect.Kind.PERCENTAGE,
        stage=PromotionEffect.Stage.ORDER,
        basis=PromotionEffect.Basis.ELIGIBLE_SUBTOTAL,
        target=PromotionEffect.Target.ORDER,
        allocation=PromotionEffect.Allocation.PRORATED,
        parameters={"rate": "20"},
    )
    return revision
