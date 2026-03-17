"""Services for deriving nutrient source metadata from product data."""

from core.models import Nutrient, Product

PROTEIN_GRAMS_THRESHOLD = 20
PROTEIN_CONCENTRATION_THRESHOLD = 0.5
CREATINE_GRAMS_THRESHOLD = 2.5
CREATINE_MILLIGRAMS_THRESHOLD = 2500
CAFFEINE_MILLIGRAMS_THRESHOLD = 50


class EnrichmentService:
    """Service to enrich products with metadata (Nutrient Sources)."""

    def enrich_product(
        self,
        product: Product,
        extra_claims: list[str] | None = None,
    ) -> None:
        """Analyzes product nutrition/components and updates `nutrient_sources` M2M.

        Args:
            product: The product to enrich.
            extra_claims: List of nutrient slugs from external sources (LLM/Scraper).

        """
        sources = set()

        if product.type == Product.Type.COMBO:
            for link in product.component_links.all():
                component = link.component
                comp_sources = self._analyze_simple_product(component)
                sources.update(comp_sources)
        else:
            sources = self._analyze_simple_product(product)

        # Merge with external claims (LLM from ingestion)
        # We process extra_claims to create Nutrients if they don't exist
        nutrient_objects = []
        if extra_claims:
            for claim_slug in extra_claims:
                nutr_obj, _ = Nutrient.objects.get_or_create(
                    slug=claim_slug,
                    defaults={"name": claim_slug.replace("-", " ").title()},
                )
                nutrient_objects.append(nutr_obj)
            sources.update(extra_claims)

        # Map heuristic sources to objects
        # Map heuristic sources to objects
        if sources or nutrient_objects:
            # We fetch existing ones for heuristic claims (safety check)
            # OR we could just get_or_create all?
            # Let's stick to get_or_create for consistency if we trust the slug.
            # But the heuristic ones ('protein', 'creatine', 'caffeine') are standard.

            # Combine the explicitly created ones with the heuristic ones
            heuristic_slugs = sources - set(extra_claims or [])
            if heuristic_slugs:
                for h_slug in heuristic_slugs:
                    nutr_obj, _ = Nutrient.objects.get_or_create(
                        slug=h_slug,
                        defaults={"name": h_slug.title()},
                    )
                    nutrient_objects.append(nutr_obj)

            # Deduplicate by ID just in case
            unique_nutrients = {n.id: n for n in nutrient_objects}.values()
            product.nutrient_sources.set(unique_nutrients)
        else:
            product.nutrient_sources.clear()

    def _analyze_simple_product(self, product: Product) -> set[str]:
        sources = set()

        # Heuristic Analysis
        for profile in product.nutrition_profiles.all():
            facts = profile.nutrition_facts
            serving = facts.serving_size_grams

            if serving <= 0:
                continue

            if (
                facts.proteins > PROTEIN_GRAMS_THRESHOLD
                or (facts.proteins / serving) > PROTEIN_CONCENTRATION_THRESHOLD
            ):
                sources.add("protein")

            for micro in facts.micronutrients.all():
                name_lower = micro.name.lower()
                val = micro.value

                is_creatine = "creatina" in name_lower or "creatine" in name_lower
                if is_creatine and (
                    (micro.unit == "g" and val >= CREATINE_GRAMS_THRESHOLD)
                    or (
                        micro.unit == "mg"
                        and val >= CREATINE_MILLIGRAMS_THRESHOLD
                    )
                ):
                    sources.add("creatine")

                if ("cafeina" in name_lower or "caffeine" in name_lower) and (
                    micro.unit == "mg" and val >= CAFFEINE_MILLIGRAMS_THRESHOLD
                ):
                    sources.add("caffeine")

        return sources
