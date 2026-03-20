# Domain Docs

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
- [Admin Use Cases](./admin.md)
- [Agent Use Cases](./agent.md)
- [Public Use Cases](./public.md)
- [Internal Use Cases](./internal.md)

## Use case index

### Admin

- [UC-01 Manage Brands](./admin.md#uc-01-manage-brands)
- [UC-02 Manage Stores](./admin.md#uc-02-manage-stores)
- [UC-03 Manage Flavors](./admin.md#uc-03-manage-flavors)
- [UC-04 Manage Tags](./admin.md#uc-04-manage-tags)
- [UC-05 Manage Categories](./admin.md#uc-05-manage-categories)
- [UC-06 Manage API Keys](./admin.md#uc-06-manage-api-keys)
- [UC-07 Manage Product From Admin](./admin.md#uc-07-manage-product-from-admin)
- [UC-08 Manage Product Nutrition From Admin](./admin.md#uc-08-manage-product-nutrition-from-admin)
- [UC-09 Manage Product Store Listings From Admin](./admin.md#uc-09-manage-product-store-listings-from-admin)

### AI agent

- [UC-01 Checkout Scraped Item For Processing](./agent.md#uc-01-checkout-scraped-item-for-processing)
- [UC-02 Create Simple Product From Agent](./agent.md#uc-02-create-simple-product-from-agent)
- [UC-03 Create Combo Product From Agent](./agent.md#uc-03-create-combo-product-from-agent)
- [UC-04 Link Scraped Item To Product Store From Agent](./agent.md#uc-04-link-scraped-item-to-product-store-from-agent)

### Public

- [UC-01 Subscribe To Alerts](./public.md#uc-01-subscribe-to-alerts)
- [UC-02 Query Public Catalog](./public.md#uc-02-query-public-catalog)

### Internal

- [UC-01 Link Scraped Item To Product Store](./internal.md#uc-01-link-scraped-item-to-product-store)

## Scope notes

- These use cases describe the current implemented behavior, not a future idealized
  domain model.
- `ProductAdmin` is the official manager-facing interface for product metadata,
  nutrition, and store listings.
- GraphQL acts as a thin boundary over the same service/query workflows.
