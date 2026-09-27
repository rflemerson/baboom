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
- A combo ranks through `ComboActive`: the mass of an active summed over its
  components (quantity x net mass x the component's smallest fraction across
  labels). A row exists only when every component contains the active, because
  the combo's price buys all of them and the store does not split it. A mixed
  combo is therefore listed without a metric for an active one component lacks,
  like a simple product without that active.
- Nutrition macros are nullable: a partially extracted label is stored as-is,
  because an unknown value is not a measured zero.
- Actives: `Active` names a substance the catalog ranks by. Protein is one row,
  not a privileged column; label columns point at their active through
  `nutrition_field`, and everything else is a `NutritionActive` row.
- A product is one package with one nutrition table: `ProductNutrition` (the
  table and the flavors that print it) is at most one per product. Natural and a
  flavored whey sold on the same page print different tables, so they are two
  products.
- `ProductActive` stores the dimensionless mass fraction of each active in a
  product's `ProductNutrition`, derived only from its table. Run
  `sync_product_actives` to rebuild it. `Category.default_active` names the
  active a category is ranked by.
- Units: a stored value is the number printed on the package, in the unit the
  package prints it in. That unit belongs to the field (`Product.net_mass` in g,
  `NutritionFacts.LABEL_UNITS`: g for serving and macros, mg for sodium, kcal for
  energy) or travels with the row (`NutritionActive.declared_unit`), and every
  field names its unit in its label. Nothing converts on the way in or out;
  `core/units.py` converts only inside arithmetic, into grams. Values the
  catalog cannot convert -- international units, percentages of a daily value
  -- carry no concentration and simply do not rank.
- Store links: `ProductStore` links a product to a captured `Offer`, one link
  per offer and as many offers per product as flavors and stores sell it. The
  rules live in `ProductStore.clean()`: the store comes from the offer through
  `Store.scraper_slug`, the offer must still be listed, and once the product's
  table lists flavors, the flavor the offer states (`Offer.flavors`) must be one
  of them. A product whose table is not in yet takes any single-flavor offer, so
  a price never waits for the label. A product shows its cheapest listed offer.
- Product create/update goes through `ProductCreateService` and `ProductMetadataUpdateService`.

## Public

- Alerts use `AlertSubscriptionService`.
- Catalog reads use `/api/catalog/`, `core/selectors.py`, pagination, filters, sorting, derived metrics, and cache headers.
- Catalog metrics are relative to one active and one mass unit; the response
  names both in `active` and `massUnit` rather than implying them. Pass `active`
  to rank by another substance; an unknown slug yields empty metrics.
- Each catalog row is one product and includes `nutritionProfile` with its ID,
  nutrition table ID and the flavors that print it. A product without a table
  has `nutritionProfile: null` and no nutritional metrics.
- `price` and `externalLink` come from the cheapest listed offer linked to the
  product, which sells one of the flavors its table lists.

## Scraped evidence

- Scraper monitors store merchant offers and `ScrapedItem` source links.
- A `ScrapedPage` holds the store, the URL and the `api_context` the catalog
  crawl collected. It points at a page; it does not copy one. Nothing here
  stores page HTML: a curator opens the live page, which is truer than a
  stored copy and costs nothing to keep.
- `ScrapedPageAdmin` is read-only and forbids adding, so a page is inspected
  in Django admin and changed only by the crawl that produced it.
- `ensure_catalog_operator --username=<name>` keeps a staff user in the
  `catalog-operator` group with an explicit, delete-free permission set. It is a
  command rather than a migration because access is configuration, not schema.
- The scraped-item admin action opens the store link form with the item's offer
  chosen, or the existing link if the offer is already linked.
- Product creation, offer linking, nutrition profiles, flavors, components and
  publication are human catalog actions in Django admin.


## Services

- `ProductCreateService`, `ProductMetadataUpdateService`
- `AlertSubscriptionService`
- `ScraperService` for offer snapshots
- `public_catalog_products(...)` in `core/selectors.py`
