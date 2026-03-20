# Core Domain Docs

This directory documents the core use cases of the API domain using a simple,
literature-friendly format:

- goal
- primary actor
- supporting actors
- trigger
- preconditions
- postconditions
- main success flow
- alternate flows
- business rules

## Reference docs

- [Service Map](./SERVICE_MAP.md)
- [Admin Use Cases](./use_cases/admin.md)
- [Agent Use Cases](./use_cases/agent.md)
- [Public Use Cases](./use_cases/public.md)
- [Internal Use Cases](./use_cases/internal.md)

## Use case index

### Admin

- [UC-01 Manage Brands](./use_cases/admin.md#uc-01-manage-brands)
- [UC-02 Manage Stores](./use_cases/admin.md#uc-02-manage-stores)
- [UC-03 Manage Flavors](./use_cases/admin.md#uc-03-manage-flavors)
- [UC-04 Manage Tags](./use_cases/admin.md#uc-04-manage-tags)
- [UC-05 Manage Categories](./use_cases/admin.md#uc-05-manage-categories)
- [UC-06 Manage API Keys](./use_cases/admin.md#uc-06-manage-api-keys)
- [UC-07 Manage Product From Admin](./use_cases/admin.md#uc-07-manage-product-from-admin)
- [UC-08 Manage Product Nutrition From Admin](./use_cases/admin.md#uc-08-manage-product-nutrition-from-admin)
- [UC-09 Manage Product Store Listings From Admin](./use_cases/admin.md#uc-09-manage-product-store-listings-from-admin)

### AI agent

- [UC-01 Checkout Scraped Item For Processing](./use_cases/agent.md#uc-01-checkout-scraped-item-for-processing)
- [UC-02 Create Simple Product From Agent](./use_cases/agent.md#uc-02-create-simple-product-from-agent)
- [UC-03 Create Combo Product From Agent](./use_cases/agent.md#uc-03-create-combo-product-from-agent)
- [UC-04 Link Scraped Item To Product Store From Agent](./use_cases/agent.md#uc-04-link-scraped-item-to-product-store-from-agent)

### Public

- [UC-01 Subscribe To Alerts](./use_cases/public.md#uc-01-subscribe-to-alerts)
- [UC-02 Query Public Catalog](./use_cases/public.md#uc-02-query-public-catalog)

### Internal

- [UC-01 Link Scraped Item To Product Store](./use_cases/internal.md#uc-01-link-scraped-item-to-product-store)

## Scope notes

- These use cases describe the current implemented behavior, not a future idealized
  domain model.
- `ProductAdmin` is the official manager-facing interface for product metadata,
  nutrition, and store listings.
- GraphQL acts as a thin boundary over the same service/query workflows.
