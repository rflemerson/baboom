# Domain

## Boundaries

- Admin owns catalog curation.
- REST owns public catalog and alert flows.
- GraphQL owns authenticated local review, staging, and explicit catalog approval.
- Selectors own read/query composition.

## Admin

- Products: create, edit, publish/unpublish, delete with related store links.
- Support data: brands, stores, flavors, tags, categories, alert subscribers, API keys.
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
- `ProductActive` stores the dimensionless mass fraction of each active in a
  product, derived from its nutrition profiles and refreshed on every write. Run
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

## Local review

- `checkoutScrapedItem` locks one eligible item and marks it `PROCESSING`.
- `submitAgentExtraction` stores review data in `ScrapedItemExtraction` and moves the item to `REVIEW`.
- `reportScrapedItemError` records retryable/fatal failures.
- Agent extraction never creates catalog products.
- GraphQL stays protected by `IsAuthenticatedWithAPIKey`.
- `reviewQueue` lists queued items by default; pass a status to filter or `null`
  to inspect all states. `reviewItem` and `reviewExtraction` resume without mutation.
- `checkoutScrapedItem(data: {itemId: ...})` reserves one queued item. Omitting
  the target reserves the next queued item. Failed work must be requeued in admin.
- `heartbeatScrapedItem` refreshes processing activity. `releaseScrapedItem`
  returns it to the queue; the periodic timeout task also requeues expired work.
- `ignoreScrapedItem` accepts queued, processing, and review items.
- `submitAgentExtraction` accepts processing or review items, so a reviewer can
  revise a staged draft. It never changes catalog records.
- `catalogCandidates` searches published and unpublished products by name/brand
  and/or exact EAN. `catalogBrands`, `catalogCategories`, and `catalogTags` expose
  valid reference IDs.
- `approveScrapedItem` requires review state and a staged extraction, plus exactly
  one of `productId` or `createProduct`. Equivalent retries return the linked
  product; conflicting retries fail. Product creation and offer linking are atomic.
- `approveScrapedItem` submits a mass as `netMass` plus `massUnit`; the service
  converts it before it reaches the catalog. Extraction staging keeps the units
  the page stated, since it is a transcript of the source.
- Remote creation validates references and product fields and always creates an
  unpublished product. `isPublished: true` is rejected. Publication, nutrition,
  flavors, and component curation stay in admin; the complete extracted tree stays
  available in staging and is not automatically materialized into catalog relations.
- API keys identify trusted review clients. Reservations are item state, not
  per-user ownership tokens; operators sharing access must coordinate item use.
- Review clients receive JSON `sourcePageContext`, `sourcePageStructuredData`, and
  normalized `imageUrls`; string context fields remain available to existing clients.

## Services

- `ProductCreateService`, `ProductMetadataUpdateService`, `ProductStoreService`
- `AlertSubscriptionService`
- `ScrapedItemCheckoutService`, `ScrapedItemExtractionSubmitService`, `ScrapedItemErrorService`
- `ScrapedItemReviewStateService`, `ScrapedItemApprovalService`
- `public_catalog_products(...)` in `core/selectors.py`
