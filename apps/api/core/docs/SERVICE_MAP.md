# Service Map

This document maps the main use cases to the current service layer.

## ProductCreateService

### Owns

- [UC-07 Manage Product From Admin](./use_cases/admin.md#uc-07-manage-product-from-admin)
- [UC-02 Create Simple Product From Agent](./use_cases/agent.md#uc-02-create-simple-product-from-agent)
- [UC-03 Create Combo Product From Agent](./use_cases/agent.md#uc-03-create-combo-product-from-agent)

### Collaborates with

- `ProductStoreService`
- `ProductNutritionService`
- `ComboResolutionService`

## ProductMetadataUpdateService

### Owns

- [UC-07 Manage Product From Admin](./use_cases/admin.md#uc-07-manage-product-from-admin)

## ProductNutritionService

### Owns

- [UC-08 Manage Product Nutrition From Admin](./use_cases/admin.md#uc-08-manage-product-nutrition-from-admin)

## ProductStoreService

### Owns

- [UC-09 Manage Product Store Listings From Admin](./use_cases/admin.md#uc-09-manage-product-store-listings-from-admin)

## ComboResolutionService

### Owns

- [UC-04 Manage Combo Components From Agent](./use_cases/agent.md#uc-04-manage-combo-components-from-agent)

### Supports

- [UC-03 Create Combo Product From Agent](./use_cases/agent.md#uc-03-create-combo-product-from-agent)

## scrapers.services.ScrapedItemLinkService

### Owns

- [UC-01 Link Scraped Item To Product](./use_cases/internal.md#uc-01-link-scraped-item-to-product)

### Supports

- Explicit scraped-item linking workflows driven by admin or agent decisions

## AlertSubscriptionService

### Owns

- [UC-01 Subscribe To Alerts](./use_cases/public.md#uc-01-subscribe-to-alerts)

## Query layer

### Public catalog query flow

- [UC-02 Query Public Catalog](./use_cases/public.md#uc-02-query-public-catalog)

### Current implementation

- `selectors.py`
- GraphQL query boundary
