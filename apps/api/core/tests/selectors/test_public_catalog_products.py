"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from django.test import TestCase
from django.utils import timezone
from django.utils.text import slugify

from core.dtos import (
    CatalogProductsFilters,
)
from core.models import (
    Active,
    Brand,
    Flavor,
    NutritionActive,
    NutritionFacts,
    Product,
    ProductComponent,
    ProductNutrition,
    ProductStore,
    Store,
)
from core.selectors import (
    catalog_active,
)
from core.tests.helpers import (
    CatalogAnnotatedProduct,
    _link_offer,
    projected_catalog,
    projected_catalog_with_stats,
    store_seller,
)
from offers.models import Offer, StockStatus
from pricing.projections import ProjectionService


class CatalogActiveRankingTests(TestCase):
    """Coverage for ranking the catalog by different actives."""

    def setUp(self) -> None:
        """Create two products that rank differently per active."""
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.creatine = Active.objects.create(
            name="Creatine",
            slug="creatine",
            display_unit="g",
        )

        self.whey = self._product("Whey", proteins=Decimal(24), creatine=None)
        self.blend = self._product("Blend", proteins=Decimal(12), creatine=Decimal(5))

    def _product(
        self,
        name: str,
        proteins: Decimal,
        creatine: Decimal | None,
    ) -> Product:
        """Create a published 1kg product with one nutrition profile."""
        product = Product.objects.create(
            name=name,
            brand=self.brand,
            net_mass=Decimal(1000),
            is_published=True,
        )
        facts = NutritionFacts.objects.create(
            serving_size=Decimal(30),
            proteins=proteins,
        )
        if creatine is not None:
            NutritionActive.objects.create(
                nutrition_facts=facts,
                active=self.creatine,
                amount=creatine,
                declared_unit="g",
            )
        ProductNutrition.objects.create(product=product, nutrition_facts=facts)
        _link_offer(
            product=product,
            store=Store.objects.create(
                name=name,
                display_name=name,
                scraper_slug=slugify(name),
            ),
            product_link=f"https://example.com/{name}",
            price=100.00,
        )
        return product

    def test_default_active_ranks_by_protein(self) -> None:
        """Without an explicit active the catalog uses the configured default."""
        results = list(projected_catalog())

        assert [product.name for product in results] == ["Whey", "Blend"]

    def test_missing_current_price_hides_old_observation_from_catalog(self) -> None:
        """A price-less or delisted offer must not surface yesterday's price."""
        link = self.whey.store_links.get()
        assert link.offer is not None
        link.offer.current_price = None
        link.offer.save(update_fields=["current_price"])

        row = projected_catalog().get(pk=self.whey.pk)

        assert row.price is None
        assert row.external_link is None

    def test_delisted_offer_hides_old_observation_from_catalog(self) -> None:
        """An archived offer's historical price remains stored, not ranked."""
        link = self.whey.store_links.get()
        assert link.offer is not None
        link.offer.delisted_at = timezone.now()
        link.offer.save(update_fields=["delisted_at"])

        assert projected_catalog().get(pk=self.whey.pk).price is None
        assert link.offer.price_observations.count() == 1

    def test_requesting_another_active_changes_the_ranking(self) -> None:
        """The same expressions rank creatine without a per-active branch."""
        results = list(
            projected_catalog(CatalogProductsFilters(active="creatine")),
        )

        assert results[0].name == "Blend"
        assert results[0].price_per_active is not None
        assert results[1].price_per_active is None

    def test_unknown_active_slug_resolves_to_nothing(self) -> None:
        """An active the catalog does not know about yields empty metrics."""
        assert catalog_active("unobtainium") is None

        results = list(
            projected_catalog(CatalogProductsFilters(active="unobtainium")),
        )

        assert all(product.price_per_active is None for product in results)


class ComboRankingTests(TestCase):
    """A combo ranks by the active its components sum up to.

    Its price buys every component, and the store does not say how much of it
    each one costs, so a combo only has a price per active when every component
    contains that active. Otherwise it behaves like a simple product without the
    active: listed, with no metric, sorted last.
    """

    def setUp(self) -> None:
        """Create the actives and a brand shared by every product."""
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.creatine = Active.objects.create(
            name="Creatine",
            slug="creatine",
            display_unit="g",
        )

    def _simple(
        self,
        name: str,
        *,
        proteins: Decimal,
        creatine: Decimal | None = None,
    ) -> Product:
        """Create an unpublished 1kg component with a 30g serving label."""
        product = Product.objects.create(
            name=name,
            brand=self.brand,
            net_mass=Decimal(1000),
        )
        self._label(product, proteins=proteins, creatine=creatine)
        return product

    def _label(
        self,
        product: Product,
        *,
        proteins: Decimal,
        creatine: Decimal | None = None,
    ) -> ProductNutrition:
        """Attach one more nutrition profile to a product."""
        facts = NutritionFacts.objects.create(
            serving_size=Decimal(30),
            proteins=proteins,
        )
        if creatine is not None:
            NutritionActive.objects.create(
                nutrition_facts=facts,
                active=self.creatine,
                amount=creatine,
                declared_unit="g",
            )
        return ProductNutrition.objects.create(product=product, nutrition_facts=facts)

    def _combo(self, name: str, components: list[tuple[Product, int]]) -> Product:
        """Create a published combo priced at 100."""
        combo = Product.objects.create(
            name=name,
            brand=self.brand,
            kind=Product.Kind.COMBO,
            is_published=True,
        )
        for component, quantity in components:
            ProductComponent.objects.create(
                parent=combo,
                component=component,
                quantity=quantity,
            )
        _link_offer(
            product=combo,
            store=Store.objects.create(
                name=name,
                display_name=name,
                scraper_slug=slugify(name),
            ),
            price=100.00,
        )
        return combo

    def _price_per_gram(
        self, combo: Product, active: str = "protein"
    ) -> Decimal | None:
        row = projected_catalog(CatalogProductsFilters(active=active)).get(
            pk=combo.pk,
        )
        if row.price_per_active is None:
            return None
        return Decimal(str(row.price_per_active)).quantize(Decimal("0.0001"))

    def test_combo_ranks_by_the_protein_its_components_sum_to(self) -> None:
        """Two 1kg tubs at 80% protein hold 1600g, so 100 buys 0.0625 per gram."""
        whey = self._simple("Whey", proteins=Decimal(24))
        combo = self._combo("Two Wheys", [(whey, 2)])

        assert self._price_per_gram(combo) == Decimal("0.0625")

    def test_a_combo_has_no_metric_for_an_active_one_component_lacks(self) -> None:
        """Protein is in both components; creatine only in one."""
        whey = self._simple("Whey", proteins=Decimal(24))
        blend = self._simple("Blend", proteins=Decimal(12), creatine=Decimal(5))
        combo = self._combo("Whey and Blend", [(whey, 1), (blend, 1)])

        assert self._price_per_gram(combo, "creatine") is None
        assert self._price_per_gram(combo, "protein") == Decimal("0.0833")

    def test_deleting_a_component_product_updates_the_combo(self) -> None:
        """Cascade removes the link without calling its delete() method."""
        whey = self._simple("Whey", proteins=Decimal(24))
        blend = self._simple("Blend", proteins=Decimal(12))
        combo = self._combo("Whey and Blend", [(whey, 1), (blend, 1)])

        blend.delete()

        assert self._price_per_gram(combo) == Decimal("0.1250")

    def test_removing_a_component_by_queryset_updates_the_combo(self) -> None:
        """A queryset delete never calls the model's delete() method."""
        whey = self._simple("Whey", proteins=Decimal(24))
        blend = self._simple("Blend", proteins=Decimal(12))
        combo = self._combo("Whey and Blend", [(whey, 1), (blend, 1)])

        combo.component_links.filter(component=blend).delete()

        assert self._price_per_gram(combo) == Decimal("0.1250")

    def test_removing_a_label_by_queryset_updates_the_combo(self) -> None:
        """Dropping a table by queryset still refreshes the combo total."""
        whey = self._simple("Whey", proteins=Decimal(24))
        combo = self._combo("Two Wheys", [(whey, 2)])
        assert self._price_per_gram(combo) == Decimal("0.0625")

        whey.nutrition_profiles.all().delete()

        assert self._price_per_gram(combo) is None

    def test_removing_a_component_updates_the_combo(self) -> None:
        """The derived total follows the component list."""
        whey = self._simple("Whey", proteins=Decimal(24))
        blend = self._simple("Blend", proteins=Decimal(12))
        combo = self._combo("Whey and Blend", [(whey, 1), (blend, 1)])

        combo.component_links.get(component=blend).delete()

        assert self._price_per_gram(combo) == Decimal("0.1250")

    def test_changing_a_component_mass_updates_the_combo(self) -> None:
        """Net mass is half of the arithmetic, so it must trigger a resync."""
        whey = self._simple("Whey", proteins=Decimal(24))
        combo = self._combo("Two Wheys", [(whey, 2)])

        whey.net_mass = Decimal(1500)
        whey.save()

        assert self._price_per_gram(combo) == Decimal("0.0417")


class ProductStatsTests(TestCase):
    """Tests for the public catalog selector annotations."""

    def setUp(self) -> None:
        """Set up test data."""
        self.brand = Brand.objects.create(name="Test Brand", display_name="Test Brand")
        self.store = Store.objects.create(
            name="Test Store",
            display_name="Test Store",
            scraper_slug="test_store",
        )

        self.product = Product.objects.create(
            name="Whey Protein",
            brand=self.brand,
            net_mass=Decimal(1000),
        )

        self.nutrition = NutritionFacts.objects.create(
            serving_size=Decimal(30),
            proteins=Decimal("24.0"),
            carbohydrates=Decimal(0),
            total_fats=Decimal(0),
            description="Standard Whey",
            energy=120,
        )
        self.profile = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.nutrition,
        )

        self.link = _link_offer(
            product=self.product,
            store=self.store,
            product_link="https://example.com",
            price=100.00,
        )

    def test_active_calculations(self) -> None:
        """Derived metrics should be annotated for the catalog's default active."""
        product = cast(
            "CatalogAnnotatedProduct | None",
            projected_catalog_with_stats().first(),
        )

        assert product is not None
        assert product.concentration == Decimal("80.0")
        assert product.total_active == Decimal(800)
        assert round(product.price_per_active, 3) == Decimal("0.125")
        assert product.external_link == "https://example.com"

    def test_missing_price_handling(self) -> None:
        """Products without price should keep nullable metrics."""
        product_without_price = Product.objects.create(
            name="No Price Whey",
            brand=self.brand,
            net_mass=Decimal(500),
        )

        result = cast(
            "CatalogAnnotatedProduct | None",
            projected_catalog_with_stats()
            .filter(
                pk=product_without_price.pk,
            )
            .first(),
        )

        assert result is not None
        assert result.price is None
        assert result.price_per_active is None
        assert result.external_link is None

    def test_price_and_link_come_from_the_same_offer_when_prices_tie(
        self,
    ) -> None:
        """Two stores at the same price never mix one's price with the other's URL."""
        second_store = Store.objects.create(
            name="Second Store",
            display_name="Second Store",
            scraper_slug="second_store",
        )
        _link_offer(
            product=self.product,
            store=second_store,
            product_link="https://example.com/second",
            price=100.00,
        )

        product = cast(
            "CatalogAnnotatedProduct | None",
            projected_catalog_with_stats().get(pk=self.product.pk),
        )

        assert product is not None
        assert product.price == Decimal("100.00")
        assert product.external_link == self.link.offer.url

    def test_rest_ranks_and_filters_flavors_with_their_own_table(self) -> None:
        """Search and filters select the product whose table a flavor prints."""
        self.product.is_published = True
        self.product.save()
        self.profile.flavors.add(Flavor.objects.create(name="Chocolate"))
        vanilla = Product.objects.create(
            name="Whey Protein Baunilha",
            brand=self.brand,
            net_mass=Decimal(1000),
            is_published=True,
        )
        ProductNutrition.objects.create(
            product=vanilla,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(21),
            ),
        ).flavors.add(Flavor.objects.create(name="Vanilla"))
        ProjectionService().refresh()

        payload = self.client.get("/api/catalog/products/").json()
        assert [row["id"] for row in payload["items"]] == [self.product.pk, vanilla.pk]
        assert [row["nutritionProfile"]["flavors"] for row in payload["items"]] == [
            ["Chocolate"],
            ["Vanilla"],
        ]
        assert [Decimal(row["concentration"]) for row in payload["items"]] == [
            Decimal(80),
            Decimal(70),
        ]
        searched = self.client.get("/api/catalog/products/", {"search": "Vanilla"})
        assert [row["id"] for row in searched.json()["items"]] == [vanilla.pk]
        filtered = self.client.get(
            "/api/catalog/products/",
            {"search": "Vanilla", "concentration_min": 75},
        ).json()
        assert filtered["items"] == []
        price_filtered = self.client.get(
            "/api/catalog/products/",
            {"price_per_active_max": 0.13},
        ).json()
        assert [row["id"] for row in price_filtered["items"]] == [self.product.pk]

    def test_same_table_flavors_share_one_catalog_row(self) -> None:
        """Several flavors of one profile must not duplicate ranking entries."""
        self.product.is_published = True
        self.product.save()
        profile = self.product.nutrition_profiles.get()
        profile.flavors.add(
            Flavor.objects.create(name="Chocolate"),
            Flavor.objects.create(name="Chocolate Hazelnut"),
        )
        payload = self.client.get(
            "/api/catalog/products/",
            {"search": "Chocolate"},
        ).json()
        assert payload["pageInfo"]["totalCount"] == 1
        assert payload["items"][0]["nutritionProfile"]["flavors"] == [
            "Chocolate",
            "Chocolate Hazelnut",
        ]

    def test_catalog_sorting_is_stable_when_metric_values_tie(self) -> None:
        """Sorting should use a stable fallback under metric ties."""
        alpha_brand = Brand.objects.create(name="Alpha", display_name="Alpha")
        beta_brand = Brand.objects.create(name="Beta", display_name="Beta")
        alpha = Product.objects.create(
            name="Whey A",
            brand=alpha_brand,
            net_mass=Decimal(1000),
            is_published=True,
        )
        beta = Product.objects.create(
            name="Whey B",
            brand=beta_brand,
            net_mass=Decimal(1000),
            is_published=True,
        )

        for product in (alpha, beta):
            ProductNutrition.objects.create(
                product=product,
                nutrition_facts=self.nutrition,
            )

        _link_offer(
            product=alpha,
            store=self.store,
            product_link="https://example.com/alpha",
            price=100.00,
        )
        _link_offer(
            product=beta,
            store=self.store,
            product_link="https://example.com/beta",
            price=100.00,
        )

        items = list(
            projected_catalog(
                CatalogProductsFilters(sort_by="price", sort_dir="asc"),
            ).values_list("brand__name", "name"),
        )

        assert items[:2] == [("Alpha", "Whey A"), ("Beta", "Whey B")]


class CatalogRowPriceTests(TestCase):
    """Natural and the flavored whey of one page are two priced products."""

    def setUp(self) -> None:
        """Create both products of the Growth 1 kg page, each with its table."""
        Store.objects.create(
            name="Growth", display_name="Growth", scraper_slug="growth"
        )
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.natural = self._product("Whey 1 kg Natural", "Natural")
        self.flavored = self._product("Whey 1 kg", "Chocolate", "Morango")

    def _product(self, name: str, *flavors: str) -> Product:
        """Create a published product whose one table the flavors print."""
        product = Product.objects.create(
            name=name,
            brand=self.brand,
            net_mass=Decimal(1000),
            is_published=True,
        )
        profile = ProductNutrition.objects.create(
            product=product,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(24),
            ),
        )
        profile.flavors.set(
            [Flavor.objects.get_or_create(name=flavor)[0] for flavor in flavors],
        )
        return product

    def _sell(self, product: Product, flavor: str, price: str) -> None:
        """Link the captured offer of one flavor to its product."""
        offer = Offer.objects.create(
            seller_account=store_seller("growth"),
            store_slug="growth",
            external_id=flavor,
            url=f"https://growth.example/{flavor}",
            current_price=Decimal(price),
            current_stock_status=StockStatus.AVAILABLE,
            options=[{"name": "Sabor", "value": flavor}],
        )
        ProductStore.objects.create(product=product, offer=offer)

    def _row(self, product: Product) -> CatalogAnnotatedProduct:
        """Return the catalog row of one product."""
        return projected_catalog().get(pk=product.pk)

    def test_each_product_shows_the_price_of_its_own_flavors(self) -> None:
        """The Natural product never borrows the flavored price, nor the reverse."""
        self._sell(self.natural, "Natural", "150.00")
        self._sell(self.flavored, "Chocolate", "190.00")

        assert self._row(self.natural).price == Decimal("150.00")
        assert self._row(self.flavored).price == Decimal("190.00")
        assert self._row(self.natural).external_link == "https://growth.example/Natural"

    def test_a_product_sold_in_several_flavors_shows_the_cheapest(self) -> None:
        """Flavors sharing one table compete; the product offers the best price."""
        self._sell(self.flavored, "Chocolate", "190.00")
        self._sell(self.flavored, "Morango", "170.00")

        row = self._row(self.flavored)

        assert row.price == Decimal("170.00")
        assert row.external_link == "https://growth.example/Morango"


class CatalogAvailabilityTests(TestCase):
    """A product is priced by what can be bought now, and stays listed regardless."""

    def setUp(self) -> None:
        """Create a published, labelled product sold by one store."""
        Store.objects.create(
            name="Growth", display_name="Growth", scraper_slug="growth"
        )
        self.product = Product.objects.create(
            name="Whey 1 kg",
            brand=Brand.objects.create(name="growth", display_name="Growth"),
            net_mass=Decimal(1000),
            is_published=True,
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(24),
            ),
        )

    def _sell(self, external_id: str, price: str, stock: str) -> None:
        """Link an offer with the given price and stock reading."""
        offer = Offer.objects.create(
            seller_account=store_seller("growth"),
            store_slug="growth",
            external_id=external_id,
            url=f"https://growth.example/{external_id}",
            current_price=Decimal(price),
            current_stock_status=stock,
        )
        ProductStore.objects.create(product=self.product, offer=offer)

    def test_an_offer_of_unknown_stock_never_wins(self) -> None:
        """A source that said nothing about stock has not said it is buyable."""
        self._sell("unknown", "80.00", StockStatus.UNKNOWN)
        self._sell("in-stock", "120.00", StockStatus.AVAILABLE)

        row = projected_catalog().get(pk=self.product.pk)

        assert row.price == Decimal("120.00")

    def test_a_sold_out_offer_never_wins_over_one_in_stock(self) -> None:
        """The cheapest price must be one the buyer can actually pay."""
        self._sell("sold-out", "90.00", StockStatus.OUT_OF_STOCK)
        self._sell("in-stock", "120.00", StockStatus.AVAILABLE)

        row = projected_catalog().get(pk=self.product.pk)

        assert row.price == Decimal("120.00")
        assert row.external_link == "https://growth.example/in-stock"

    def test_a_product_with_only_sold_out_offers_stays_listed_without_price(
        self,
    ) -> None:
        """Publication is editorial; a missing price is not a missing product."""
        self._sell("sold-out", "90.00", StockStatus.OUT_OF_STOCK)

        row = projected_catalog().get(pk=self.product.pk)

        assert row.price is None
        assert row.external_link is None
