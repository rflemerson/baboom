# Domain

## Boundaries

- Admin owns catalog curation.
- REST owns public catalog and alert flows.
- GraphQL owns authenticated scraper-agent workflow only.
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

## Agent

- `checkoutScrapedItem` locks one eligible item and marks it `PROCESSING`.
- `submitAgentExtraction` stores review data in `ScrapedItemExtraction` and moves the item to `REVIEW`.
- `reportScrapedItemError` records retryable/fatal failures.
- Agent extraction never creates catalog products.
- GraphQL stays protected by `IsAuthenticatedWithAPIKey`.

## Services

- `ProductCreateService`, `ProductMetadataUpdateService`, `ProductStoreService`
- `AlertSubscriptionService`
- `ScrapedItemCheckoutService`, `ScrapedItemExtractionSubmitService`, `ScrapedItemErrorService`
- `public_catalog_products(...)` in `core/selectors.py`
