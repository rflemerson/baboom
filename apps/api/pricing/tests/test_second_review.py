"""Synthetic acceptance cases from the second architecture review."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from pydantic import ValidationError

from common.testing import raised
from offers.models import Evidence, Offer
from pricing.costs import CostBook
from pricing.domain.engine import evaluate
from pricing.domain.types import (
    CartLine,
    CompatibilityFact,
    RewardTermsFact,
    RouteFact,
    ShippingFact,
)
from pricing.facts import FactLoader
from pricing.models import (
    OfferScenarioProjection,
    PricingPolicyRevision,
    ShippingQuote,
    TaxFeeQuote,
)
from pricing.projections import ProjectionService
from pricing.services import PricingService, QuoteRequest
from pricing.tests.domain.builders import (
    NOW,
    context,
    effect,
    inputs,
    offer,
    policy,
    price,
    revision,
)
from pricing.tests.projections.test_projections import URL, TwoProductCatalog
from promotions.models import (
    ActivationCode,
    Promotion,
    PromotionEffect,
    PromotionRevision,
    PromotionScope,
    PurchaseRoute,
)
from promotions.services import PromotionService
from scrapers.contracts import PriceInput, ScrapedProductInput
from scrapers.services import ScraperService

MIN_QUANTITY = 10
PROGRAM_ID = 7


class SecondReviewTests(SimpleTestCase):
    """Restrictions, expiry and application limits must survive evaluation."""

    def test_adapter_preserves_quantity_restrictions(self) -> None:
        """A02: a ten-unit price is not an unrestricted public price."""
        value = PriceInput.model_validate(
            {
                "role": "payable",
                "amount": "1",
                "source_field": "synthetic",
                "quantity_min": 10,
                "context": {"program_id": 7},
            }
        )
        assert value.quantity_min == MIN_QUANTITY
        assert value.context.program_id == PROGRAM_ID

    def test_unknown_adapter_restriction_is_rejected(self) -> None:
        """An unrecognized restriction cannot disappear silently."""
        raised(
            lambda: PriceInput.model_validate(
                {
                    "role": "payable",
                    "amount": "1",
                    "source_field": "synthetic",
                    "mystery_restriction": True,
                }
            ),
            ValidationError,
        )

    def test_fixed_discount_per_line_respects_application_limit(self) -> None:
        """A07: two lines with one application receive only ten off."""
        result = evaluate(
            inputs(
                context=context(CartLine(1), CartLine(2)),
                offers=(offer(1), offer(2)),
                prices=(price(1, "100"), price(2, "100")),
                revisions=(
                    revision(
                        1,
                        effect(
                            "fixed_amount",
                            params={"amount": "10"},
                            allocation="per_line",
                            max_applications=1,
                        ),
                    ),
                ),
            )
        )
        assert result.merchandise_total == Decimal(190)

    def test_shipping_bounds_expiry(self) -> None:
        """A05: the earliest fact expiration limits the result."""
        deadline = NOW + timedelta(minutes=5)
        result = evaluate(
            inputs(
                prices=(price(1, "100", fresh_until=NOW + timedelta(hours=72)),),
                shipping=(ShippingFact("all", Decimal(5), "BRL", expires_at=deadline),),
            )
        )
        assert result.expires_at == deadline


class RouteIntegrationTests(TwoProductCatalog, TestCase):
    """A01: the existing card receives the URL selected by the engine."""

    def test_curated_route_reaches_rest(self) -> None:
        """The route URL and seller flag must describe the same link."""
        route_url = "https://synthetic.example/selected?seller=9&variant=2"
        with patch("pricing.invalidation.refresh_projections.delay"):
            PurchaseRoute.objects.create(
                offer=self.offers["B"],
                kind="marketplace_listing",
                url=route_url,
                fixes_seller=True,
                fixes_variant=True,
                instructions="Synthetic seller selection",
            )
        ProjectionService().refresh()
        payload = self.client.get(URL, {"scenario": "listed"}).json()
        item = next(row for row in payload["items"] if row["name"] == "B")
        assert item["externalLink"] == route_url
        assert item["linkSelectsSeller"]

    def test_current_fees_replace_previous_readings(self) -> None:
        """A04: independent charge keys sum, rereadings never do."""
        common = {
            "group_fingerprint": "synthetic-group",
            "kind": "service",
            "currency_id": "BRL",
            "inclusion": "excluded",
            "source": "synthetic",
            "expires_at": NOW + timedelta(hours=1),
        }
        TaxFeeQuote.objects.create(
            **common, amount=5, observed_at=NOW - timedelta(minutes=1)
        )
        TaxFeeQuote.objects.create(**common, amount=7, observed_at=NOW)
        _shipping, fees, _status = _costs()
        assert sum(fee.amount for fee in fees) == Decimal(7)
        TaxFeeQuote.objects.create(
            **common, amount=5, observed_at=NOW, charge_key="second"
        )
        _shipping, fees, _status = _costs()
        assert sum(fee.amount for fee in fees) == Decimal(12)

    def test_shipping_replacements_and_executable_quotes(self) -> None:
        """A06: only guaranteed old quotes survive replacement."""
        common = {
            "group_fingerprint": "synthetic-group",
            "seller_account": self.seller,
            "country": "BR",
            "currency_id": "BRL",
            "modality": "standard",
            "source": "synthetic",
            "expires_at": NOW + timedelta(hours=1),
        }
        older = ShippingQuote.objects.create(
            **common,
            amount=12,
            observed_at=NOW - timedelta(minutes=1),
        )
        ShippingQuote.objects.create(**common, amount=20, observed_at=NOW)
        shipping, _fees, _status = _costs()
        assert shipping[0].amount == Decimal(20)
        older.external_quote_id = "guaranteed-synthetic-quote"
        older.execution_guaranteed = True
        older.save()
        shipping, _fees, _status = _costs()
        assert shipping[0].amount == Decimal(12)

    def test_adapter_restrictions_reach_observations_and_engine(self) -> None:
        """A02: start with a synthetic adapter payload, never an ORM observation."""
        payload = ScrapedProductInput.model_validate(
            {
                "store_slug": "store",
                "provider": "synthetic",
                "provider_product_id": "restriction-test",
                "page_url": "https://synthetic.example/item",
                "market": {
                    "namespace": "store",
                    "channel_name": "Store",
                    "channel_kind": "independent_store",
                    "adapter": "synthetic",
                    "country": "BR",
                    "currency": "BRL",
                    "timezone": "America/Sao_Paulo",
                },
                "offers": [
                    {
                        "external_id": "restricted",
                        "stock_status": "A",
                        "variant_context": {"provider_variant_id": "restricted"},
                        "seller": {"external_id": "", "is_channel_owner": True},
                        "prices": [
                            {
                                "role": "payable",
                                "amount": "1",
                                "source_field": "synthetic",
                                "quantity_min": 10,
                                "quantity_max": 20,
                                "amount_basis": "order",
                                "context": {"program_id": PROGRAM_ID},
                            }
                        ],
                    }
                ],
            }
        )
        ScraperService.save_product_snapshot(payload)
        restricted = Offer.objects.get(external_id="restricted")
        policy_row = PricingPolicyRevision.objects.get(key="listed")
        facts = FactLoader().load([restricted.pk], policy_row)
        assert facts.prices[0].quantity_min == MIN_QUANTITY
        assert facts.prices[0].amount_basis == "order"
        assert facts.prices[0].context == (("program_id", str(PROGRAM_ID)),)
        result = PricingService().evaluate(
            QuoteRequest(
                lines=(CartLine(restricted.pk),),
                policy=policy_row,
            )
        )
        assert result.merchandise_total is None


class JointTrackingTests(SimpleTestCase):
    """A03: campaign compatibility never proves redirect compatibility."""

    def test_two_programs_need_a_joint_route(self) -> None:
        """Concurrent activation links cannot produce twenty cashback."""
        first = revision(
            1,
            effect(
                "cashback",
                stage="reward",
                reward=RewardTermsFact(
                    credited_as="money",
                    rate=Decimal(10),
                    program_id=7,
                    tracking_required=True,
                ),
            ),
            compatibility=(CompatibilityFact("promotion", "2", "allowed"),),
        )
        second = revision(
            2,
            effect(
                "cashback",
                stage="reward",
                reward=RewardTermsFact(
                    credited_as="money",
                    rate=Decimal(10),
                    program_id=8,
                    tracking_required=True,
                ),
            ),
        )
        routes = (
            RouteFact(
                1, 1, "cashback_activation", "https://synthetic.example/7", program_id=7
            ),
            RouteFact(
                2, 1, "cashback_activation", "https://synthetic.example/8", program_id=8
            ),
        )
        for revisions in ((first, second), (second, first)):
            result = evaluate(
                inputs(
                    revisions=revisions,
                    routes=routes,
                    policy=policy(allow_rewards=True),
                )
            )
            assert sum(reward.amount for reward in result.deferred_rewards) == Decimal(
                10
            )
        joint = replace(routes[0], compatible_programs=frozenset({8}))
        result = evaluate(
            inputs(
                revisions=(first, second),
                routes=(joint,),
                policy=policy(allow_rewards=True),
            )
        )
        assert sum(reward.amount for reward in result.deferred_rewards) == Decimal(20)
        assert result.purchase_routes[0].url == joint.url

    def test_objective_changes_the_chosen_combination(self) -> None:
        """Paying ninety and getting twenty later are distinct objectives."""
        discount = revision(1, effect("fixed_amount", params={"amount": "10"}))
        cashback = revision(
            2,
            effect(
                "cashback",
                stage="reward",
                reward=RewardTermsFact(
                    credited_as="money",
                    rate=Decimal(20),
                ),
            ),
        )
        base = inputs(
            revisions=(discount, cashback),
            shipping=(ShippingFact("all", Decimal(0), "BRL"),),
        )
        payable = evaluate(replace(base, policy=policy(allow_rewards=True)))
        net = evaluate(
            replace(
                base,
                policy=policy(
                    allow_rewards=True,
                    net_cost_counts_money_rewards=True,
                    objective="estimated_net_cost",
                ),
            )
        )
        assert payable.merchandise_total == Decimal(90)
        assert net.merchandise_total == Decimal(100)
        assert net.estimated_net_cost == Decimal(80)


class CouponScenarioTests(TwoProductCatalog, TestCase):
    """Compare public coupon scenarios before selecting winners and paging."""

    def test_public_coupon_changes_global_ranking(self) -> None:
        """A=100 wins by default; B=110 minus public twenty wins at ninety."""
        Offer.objects.filter(pk=self.offers["B"].pk).update(current_price=110)
        promo = Promotion.objects.create(
            title="Synthetic public coupon", issuer_seller=self.seller
        )
        revision_row = PromotionRevision.objects.create(
            promotion=promo,
            number=1,
            currency_id="BRL",
            timezone="America/Sao_Paulo",
            verified_at=timezone.now(),
            conditions={"root": {"kind": "code_required"}},
        )
        PromotionScope.objects.create(
            revision=revision_row,
            role="target",
            kind="offer",
            ref_id=self.offers["B"].pk,
        )
        PromotionEffect.objects.create(
            revision=revision_row,
            position=1,
            kind="fixed_amount",
            stage="order",
            basis="current",
            target="order",
            allocation="once",
            parameters={"amount": "20"},
        )
        ActivationCode.objects.create(
            revision=revision_row, kind="public_code", code="SYNTHETIC20"
        )
        revision_row.evidence.add(
            Evidence.objects.create(
                kind="announcement", excerpt="Synthetic coupon fixture"
            )
        )
        assert PromotionService().publish(revision_row, "executable").published
        policy_row = PricingPolicyRevision.objects.create(
            key="synthetic-coupon",
            number=1,
            scenario="listed",
            published_at=timezone.now(),
            rules={"allow_codes": True, "auto_public_codes": True},
        )
        ProjectionService().refresh()
        standard = self.client.get(
            URL,
            {
                "scenario": "listed",
                "sort_by": "price",
                "sort_dir": "asc",
                "per_page": 1,
            },
        ).json()
        coupon = self.client.get(
            URL,
            {
                "scenario": policy_row.key,
                "sort_by": "price",
                "sort_dir": "asc",
                "per_page": 1,
            },
        ).json()
        assert standard["items"][0]["name"] == "A"
        assert coupon["items"][0]["name"] == "B"
        assert Decimal(coupon["items"][0]["price"]) == Decimal(90)
        projection = OfferScenarioProjection.objects.get(
            policy=policy_row, offer=self.offers["B"], alternative="best"
        )
        assert projection.uses_coupon
        assert OfferScenarioProjection.objects.get(
            policy=policy_row, offer=self.offers["B"], alternative="coupon"
        ).comparison_amount == Decimal(90)


def _costs() -> tuple[tuple[object, ...], tuple[object, ...], str]:
    """Read the synthetic group's current costs."""
    return CostBook.load(["synthetic-group"], NOW).for_groups(
        ["synthetic-group"],
        "unknown",
    )
