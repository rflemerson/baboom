"""Markets and sellers keep identities apart that a name would merge."""

from __future__ import annotations

from django.db import IntegrityError
from django.test import TestCase

from commerce.models import Channel, Market, Program, SellerAccount
from commerce.services import CommerceIdentityService, MarketRef, SellerRef
from commerce.tests.factories import MarketFactory, SellerAccountFactory
from common.testing import raised


def _ref(namespace: str = "store", country: str = "BR") -> MarketRef:
    return MarketRef(
        namespace=namespace,
        channel_name=f"Channel {namespace}",
        channel_kind=Channel.Kind.INDEPENDENT_STORE,
        adapter="shopify",
        country=country,
        currency="BRL",
        timezone="America/Sao_Paulo",
    )


class MarketTests(TestCase):
    """A namespace names one market, with the provenance of its facts."""

    def test_market_is_created_once_per_namespace(self) -> None:
        """The second crawl finds the market the first one created."""
        first = CommerceIdentityService.market(_ref())
        second = CommerceIdentityService.market(_ref())

        assert first.pk == second.pk
        assert first.provenance == "source_contract"
        assert Market.objects.count() == 1

    def test_an_existing_market_is_never_repointed(self) -> None:
        """A namespace that meant Brazil keeps meaning Brazil."""
        CommerceIdentityService.market(_ref())
        again = CommerceIdentityService.market(_ref(country="MX"))

        assert again.country == "BR"

    def test_one_market_per_channel_and_country(self) -> None:
        """Two Brazilian markets of one channel would split its offers."""
        market = MarketFactory()
        raised(
            lambda: Market.objects.create(
                channel=market.channel,
                country="BR",
                currency=market.currency,
                timezone="America/Sao_Paulo",
                namespace="other",
            ),
            IntegrityError,
        )


class SellerTests(TestCase):
    """A seller is an id inside a market, never a name."""

    def test_same_external_id_in_two_markets_is_two_sellers(self) -> None:
        """Seller 123 of Brazil is not seller 123 of Mexico."""
        brazil, mexico = MarketFactory(), MarketFactory()
        ref = SellerRef(external_id="123", name="Loja")

        assert (
            CommerceIdentityService.seller(brazil, ref).pk
            != CommerceIdentityService.seller(mexico, ref).pk
        )

    def test_same_name_with_other_ids_is_two_sellers(self) -> None:
        """Names collide; ids do not."""
        market = MarketFactory()
        first = CommerceIdentityService.seller(market, SellerRef("1", "Loja"))
        second = CommerceIdentityService.seller(market, SellerRef("2", "Loja"))

        assert first.pk != second.pk

    def test_a_renamed_seller_keeps_its_account(self) -> None:
        """The published name is refreshed on the same account."""
        market = MarketFactory()
        first = CommerceIdentityService.seller(market, SellerRef("9", "Old"))
        renamed = CommerceIdentityService.seller(market, SellerRef("9", "New"))

        assert first.pk == renamed.pk
        assert renamed.name_raw == "New"

    def test_the_channel_owner_is_one_account_per_market(self) -> None:
        """Every crawl of a store resolves to the same owner account."""
        market = MarketFactory()
        owner = CommerceIdentityService.seller(market, SellerRef(is_channel_owner=True))
        again = CommerceIdentityService.seller(
            market,
            SellerRef(external_id="1", is_channel_owner=True),
        )

        assert owner.pk == again.pk
        assert again.external_id == "1"
        raised(
            lambda: SellerAccount.objects.create(market=market, is_channel_owner=True),
            IntegrityError,
        )

    def test_a_third_party_seller_without_an_id_is_refused(self) -> None:
        """Without an id, a seller would be matched by name."""
        raised(
            lambda: CommerceIdentityService.seller(
                MarketFactory(), SellerRef(name="Loja")
            ),
            ValueError,
        )


class ProgramTests(TestCase):
    """A programme always names who issues it."""

    def test_program_without_issuer_is_refused(self) -> None:
        """'New to the programme' needs a programme with an issuer."""
        raised(
            lambda: Program.objects.create(name="Orphan", kind="cashback", unit="BRL"),
            IntegrityError,
        )

    def test_program_issued_by_a_seller(self) -> None:
        """A store's own cashback is issued by its seller account."""
        seller = SellerAccountFactory()
        program = Program.objects.create(
            name="Store cashback",
            kind=Program.Kind.CASHBACK,
            issuer_seller=seller,
            unit="BRL",
        )

        assert program.issuer_seller == seller
