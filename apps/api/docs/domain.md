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
- Components: manage `ProductComponent` for combo products.
- Store listings: manage `ProductStore` only through the `ProductAdmin` inline.
- Product create/update goes through `ProductCreateService` and `ProductMetadataUpdateService`.
- Store listing inline rows go through `ProductStoreService`.

## Public

- Alerts use `AlertSubscriptionService`.
- Catalog reads use `/api/catalog/`, `core/selectors.py`, pagination, filters, sorting, derived metrics, and cache headers.

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
