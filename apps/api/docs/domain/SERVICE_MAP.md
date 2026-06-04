# Service Map

This document maps the main use cases to the current service layer.

## ProductCreateService

### Owns

- [UC-07 Manage Product From Admin](./admin.md#uc-07-manage-product-from-admin)

### Collaborates with

- `ProductStoreService`
- `ProductNutritionService`
- `ComboResolutionService`

## ProductMetadataUpdateService

### Owns

- [UC-07 Manage Product From Admin](./admin.md#uc-07-manage-product-from-admin)

## ProductNutritionService

### Owns

- [UC-08 Manage Product Nutrition From Admin](./admin.md#uc-08-manage-product-nutrition-from-admin)

## ProductStoreService

### Owns

- [UC-09 Manage Product Store Listings From Admin](./admin.md#uc-09-manage-product-store-listings-from-admin)

## AlertSubscriptionService

### Owns

- [UC-01 Subscribe To Alerts](./public.md#uc-01-subscribe-to-alerts)

## scrapers.services.ScrapedItemCheckoutService

### Owns

- [UC-01 Checkout Scraped Item For Processing](./agent.md#uc-01-checkout-scraped-item-for-processing)

## scrapers.services.ScrapedItemExtractionSubmitService

### Owns

- [Agent extraction staging](./agent.md#main-flow)

## scrapers.services.ScrapedItemErrorService

### Owns

- [Agent Error Flow](./agent.md#error-flow)

## REST query layer

### Public catalog query flow

- [UC-02 Query Public Catalog](./public.md#uc-02-query-public-catalog)

### Current implementation

- `selectors.py`
- REST catalog endpoints
