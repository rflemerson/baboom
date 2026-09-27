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
    public_catalog_products,
    public_catalog_products_with_stats,
)
from core.tests.helpers import (
    CatalogAnnotatedProduct,
    _link_offer,
)
from offers.models import Offer


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
        results = list(public_catalog_products())

        assert [product.name for product in results] == ["Whey", "Blend"]

    def test_missing_current_price_hides_old_observation_from_catalog(self) -> None:
        """A price-less or delisted offer must not surface yesterday's price."""
        link = self.whey.store_links.get()
        assert link.offer is not None
        link.offer.current_price = None
        link.offer.save(update_fields=["current_price"])

        row = public_catalog_products().get(pk=self.whey.pk)

        assert row.last_price is None
        assert row.external_link is None

    def test_delisted_offer_hides_old_observation_from_catalog(self) -> None:
        """An archived offer's historical price remains stored, not ranked."""
        link = self.whey.store_links.get()
        assert link.offer is not None
        link.offer.delisted_at = timezone.now()
        link.offer.save(update_fields=["delisted_at"])

        assert public_catalog_products().get(pk=self.whey.pk).last_price is None
        assert link.offer.price_observations.count() == 1

    def test_requesting_another_active_changes_the_ranking(self) -> None:
        """The same expressions rank creatine without a per-active branch."""
        results = list(
            public_catalog_products(CatalogProductsFilters(active="creatine")),
        )

        assert results[0].name == "Blend"
        assert results[0].price_per_active is not None
        assert results[1].price_per_active is None

    def test_unknown_active_slug_resolves_to_nothing(self) -> None:
        """An active the catalog does not know about yields empty metrics."""
        assert catalog_active("unobtainium") is None

        results = list(
            public_catalog_products(CatalogProductsFilters(active="unobtainium")),
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
        row = public_catalog_products(CatalogProductsFilters(active=active)).get(
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

    def test_a_component_with_several_labels_counts_its_smallest(self) -> None:
        """Flavors differ and the combo does not say which it ships."""
        whey = self._simple("Whey", proteins=Decimal(24))
        combo = self._combo("Two Wheys", [(whey, 2)])

        self._label(whey, proteins=Decimal(15))

        assert self._price_per_gram(combo) == Decimal("0.1000")

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
        """Dropping a profile by queryset still refreshes the combo total."""
        whey = self._simple("Whey", proteins=Decimal(24))
        combo = self._combo("Two Wheys", [(whey, 2)])
        self._label(whey, proteins=Decimal(15))
        assert self._price_per_gram(combo) == Decimal("0.1000")

        whey.nutrition_profiles.filter(
            nutrition_facts__proteins=Decimal(15),
        ).delete()

        assert self._price_per_gram(combo) == Decimal("0.0625")

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
        ProductNutrition.objects.create(
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
            public_catalog_products_with_stats().first(),
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
            public_catalog_products_with_stats()
            .filter(
                pk=product_without_price.pk,
            )
            .first(),
        )

        assert result is not None
        assert result.last_price is None
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
            public_catalog_products_with_stats().get(pk=self.product.pk),
        )

        assert product is not None
        assert product.last_price == Decimal("100.00")
        assert product.external_link == self.link.offer.url

    def test_catalog_preserves_distinct_nutrition_profiles(self) -> None:
        """Each label keeps its own metrics and never borrows another's price."""
        denser_profile = NutritionFacts.objects.create(
            serving_size=Decimal(30),
            proteins=Decimal("27.0"),
            carbohydrates=Decimal(0),
            total_fats=Decimal(0),
            description="Isolate profile",
            energy=120,
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=denser_profile,
        )

        products = list(
            public_catalog_products_with_stats()
            .filter(pk=self.product.pk)
            .order_by("concentration"),
        )
        assert [product.concentration for product in products] == [
            Decimal("80.0"),
            Decimal("90.0"),
        ]
        assert [product.total_active for product in products] == [
            Decimal(800),
            Decimal(900),
        ]
        assert round(products[0].price_per_active, 3) == Decimal("0.125")
        assert products[1].last_price is None
        assert products[1].price_per_active is None

    def test_rest_ranks_and_filters_flavors_with_their_own_table(self) -> None:
        """Search and concentration filters must select the same profile row."""
        self.product.is_published = True
        self.product.save()
        original = self.product.nutrition_profiles.get()
        chocolate = Flavor.objects.create(name="Chocolate")
        original.flavors.add(chocolate)
        vanilla_facts = NutritionFacts.objects.create(
            serving_size=Decimal(30),
            proteins=Decimal(21),
        )
        vanilla = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=vanilla_facts,
        )
        vanilla.flavors.add(Flavor.objects.create(name="Vanilla"))

        response = self.client.get("/api/catalog/products/")
        payload = response.json()
        assert payload["pageInfo"]["totalCount"] == len([original, vanilla])
        assert [row["nutritionProfile"]["id"] for row in payload["items"]] == [
            original.pk,
            vanilla.pk,
        ]
        assert [row["nutritionProfile"]["flavors"] for row in payload["items"]] == [
            ["Chocolate"],
            ["Vanilla"],
        ]
        assert [Decimal(row["concentration"]) for row in payload["items"]] == [
            Decimal(80),
            Decimal(70),
        ]
        searched = self.client.get(
            "/api/catalog/products/",
            {"search": "Vanilla"},
        ).json()
        assert [row["nutritionProfile"]["id"] for row in searched["items"]] == [
            vanilla.pk,
        ]
        filtered = self.client.get(
            "/api/catalog/products/",
            {"search": "Vanilla", "concentration_min": 75},
        ).json()
        assert filtered["items"] == []
        price_filtered = self.client.get(
            "/api/catalog/products/",
            {"price_per_active_max": 0.13},
        ).json()
        assert [row["nutritionProfile"]["id"] for row in price_filtered["items"]] == [
            original.pk,
        ]

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

    def test_equal_concentrations_keep_separate_profiles_and_stable_pages(self) -> None:
        """Ties and pagination must preserve identities rather than merge rows."""
        self.product.is_published = True
        self.product.save()
        original = self.product.nutrition_profiles.get()
        profile_ids = [original.pk]
        for index in range(12):
            facts = NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(24),
                description=str(index),
            )
            profile_ids.append(
                ProductNutrition.objects.create(
                    product=self.product,
                    nutrition_facts=facts,
                ).pk,
            )
        first = self.client.get("/api/catalog/products/", {"page": 1}).json()
        second = self.client.get("/api/catalog/products/", {"page": 2}).json()
        assert [
            row["nutritionProfile"]["id"] for row in first["items"] + second["items"]
        ] == profile_ids
        assert first["pageInfo"]["totalCount"] == len(profile_ids)

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
            public_catalog_products(
                CatalogProductsFilters(sort_by="last_price", sort_dir="asc"),
            ).values_list("brand__name", "name"),
        )

        assert items[:2] == [("Alpha", "Whey A"), ("Beta", "Whey B")]


class CatalogRowPriceTests(TestCase):
    """Each catalog row is priced by the offers of its own nutrition label."""

    def setUp(self) -> None:
        """Create a whey whose Natural and flavored labels sell separately."""
        self.store = Store.objects.create(
            name="Growth",
            display_name="Growth",
            scraper_slug="growth",
        )
        self.product = Product.objects.create(
            name="Whey",
            brand=Brand.objects.create(name="growth", display_name="Growth"),
            net_mass=Decimal(1000),
            is_published=True,
        )
        self.natural = self._profile("Natural")
        self.flavored = self._profile("Chocolate", "Morango")

    def _profile(self, *flavors: str) -> ProductNutrition:
        """Create a label printed by the given flavors."""
        profile = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(24),
            ),
        )
        profile.flavors.set(
            [Flavor.objects.get_or_create(name=name)[0] for name in flavors],
        )
        return profile

    def _sell(self, profile: ProductNutrition, flavor: str, price: str) -> None:
        """Link a captured offer of one flavor to its label."""
        offer = Offer.objects.create(
            store_slug="growth",
            external_id=flavor,
            url=f"https://growth.example/{flavor}",
            current_price=Decimal(price),
            options=[{"name": "Sabor", "value": flavor}],
        )
        ProductStore.objects.create(
            product=self.product,
            nutrition_profile=profile,
            offer=offer,
        )

    def _row(self, profile: ProductNutrition) -> CatalogAnnotatedProduct:
        """Return the catalog row of one label of the whey."""
        return public_catalog_products().get(nutrition_profile_id=profile.pk)

    def test_each_label_shows_the_price_of_its_own_flavors(self) -> None:
        """The Natural row never borrows the flavored price, and vice versa."""
        self._sell(self.natural, "Natural", "150.00")
        self._sell(self.flavored, "Chocolate", "190.00")

        assert self._row(self.natural).last_price == Decimal("150.00")
        assert self._row(self.flavored).last_price == Decimal("190.00")
        assert self._row(self.natural).external_link == "https://growth.example/Natural"

    def test_a_label_sold_in_several_flavors_shows_the_cheapest(self) -> None:
        """Two flavors printing one label compete; the row offers the best price."""
        self._sell(self.flavored, "Chocolate", "190.00")
        self._sell(self.flavored, "Morango", "170.00")

        row = self._row(self.flavored)

        assert row.last_price == Decimal("170.00")
        assert row.external_link == "https://growth.example/Morango"
