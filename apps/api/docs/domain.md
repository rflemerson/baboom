# Domain

## Boundaries

- Admin owns catalog curation.
- REST owns public catalog and alert flows.
- Scrapers capture merchant offers and source pages; humans curate in admin.
- Selectors own read/query composition.

## Admin

- Products: create, edit, publish/unpublish, delete with related store links.
- Support data: brands, stores, flavors, tags, categories and alert subscribers.
- Nutrition: manage `NutritionFacts`, micronutrients, and `ProductNutrition` links.
- Components: manage `ProductComponent` for products with `kind=COMBO`.
  Components are always simple products, so an assembly is one level deep and
  cannot contain itself or form a cycle. `kind` is structural and orthogonal
  to `Category`, which describes what a product is.
- Nutrition macros are nullable: a partially extracted label is stored as-is,
  because an unknown value is not a measured zero.
- Actives: `Active` names a substance the catalog ranks by. Protein is one row,
  not a privileged column; label columns point at their active through
  `nutrition_field`, and everything else is a `NutritionActive` row.
- `ProductActive` stores the dimensionless mass fraction of each active in one
  `ProductNutrition` profile, derived only from that profile's table. Concentrations
  from different labels are never merged or maximized. Run
  `sync_product_actives` to rebuild it. `Category.default_active` names the
  active a category is ranked by.
- Units: `core/units.py` declares one canonical unit per dimension and every
  conversion factor. Masses are stored in the canonical unit and converted at
  the boundary, so no column, annotation, or field name carries a unit. Values
  the catalog cannot convert -- international units, percentages of a daily
  value -- carry no concentration and simply do not rank.
- Store listings: manage `ProductStore` only through the `ProductAdmin` inline.
- Product create/update goes through `ProductCreateService` and `ProductMetadataUpdateService`.
- Store listing inline rows go through `ProductStoreService`.

## Public

- Alerts use `AlertSubscriptionService`.
- Catalog reads use `/api/catalog/`, `core/selectors.py`, pagination, filters, sorting, derived metrics, and cache headers.
- Catalog metrics are relative to one active and one mass unit; the response
  names both in `active` and `massUnit` rather than implying them. Pass `active`
  to rank by another substance; an unknown slug yields empty metrics.
- Each catalog row represents one product nutrition profile and includes
  `nutritionProfile` with its ID, nutrition table ID, and associated flavor names.
  Several flavors sharing the same profile stay together; distinct tables are
  independently filtered, sorted, and paginated. Products without profiles keep
  one row with `nutritionProfile: null` and unknown nutritional metrics.
- A row's stable identity is `(product.id, nutritionProfile.id)`. Flavor search
  matches only the corresponding profile. Offers remain linked at product level;
  the displayed price is a product offer, not a verified price for a specific flavor.

## Scraped evidence

- Scraper monitors store merchant offers and `ScrapedItem` source links.
- Page enrichment stores `ScrapedPage.api_context`, `html_structured_data`,
  `raw_html` and response metadata. Humans can inspect pages in Django admin.
- Product creation, offer linking, nutrition profiles, flavors, components and
  publication are human catalog actions in Django admin.


## Services

- `ProductCreateService`, `ProductMetadataUpdateService`, `ProductStoreService`
- `AlertSubscriptionService`
- `ScraperService` for offer snapshots and page enrichment
- `public_catalog_products(...)` in `core/selectors.py`
