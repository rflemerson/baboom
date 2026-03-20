# Agent Use Cases

This document groups the use cases handled by the AI Catalog Agent through GraphQL and scraped context.

## Actor: AI Catalog Agent

### Description

- Automated actor that uses GraphQL to create or enrich catalog content from scraped data.

### Main goals

- inspect unlinked scraped items
- decide whether to create a simple product or combo
- create products through GraphQL
- link scraped items to chosen product store listings
- submit combo component data
- drive catalog enrichment workflows from scraped context

### Main entry points

- GraphQL product creation flows
- GraphQL catalog support queries used by the agent
- unlinked scraped item workflows

## Scope

- checkout scraped items for processing
- create simple products from scraped context
- create combo products from scraped context
- link scraped items to chosen product store listings
- submit combo components during combo creation

## UC-01 Checkout Scraped Item For Processing

### Goal

Reserve the next eligible scraped item so the AI agent can inspect it and decide
what to create or enrich.

### Primary actor

- AI Catalog Agent

### Supporting actors

- Scrapers GraphQL boundary
- Scraped item lifecycle rules

### Trigger

- The agent asks the scrapers workflow for the next item to process.

### Preconditions

- At least one scraped item is eligible for checkout.

### Postconditions

- The agent receives one scraped item and that item is marked as `PROCESSING`.

### Main success flow

1. The agent requests the next scraped item to process.
2. The system filters the scraping dataset for eligible candidates.
3. The system locks the selected row for checkout.
4. The system marks the item as `PROCESSING` and updates `last_attempt_at`.
5. The system returns identifying data and source context for that item.
6. The agent uses that item to decide whether to create a simple product or combo.

### Alternate flows

#### A1. No eligible scraped items

1. The system finds no relevant candidates.
2. The system returns an empty result.

### Business rules

- Checkout is implemented in `scrapers/graphql`, not in `core/graphql`.
- Eligible items include `NEW` items and retryable `ERROR` items.
- When `force = true`, the workflow may also revisit `LINKED` or `REVIEW` items.
- Checkout marks the selected item as `PROCESSING` before returning it.

## UC-02 Create Simple Product From Agent

### Goal

Create a simple product through GraphQL from scraped context.

### Primary actor

- AI Catalog Agent

### Supporting actors

- GraphQL boundary
- ProductCreateService
- ProductNutritionService
- ProductStoreService

### Trigger

- The agent submits a new simple product through GraphQL.

### Preconditions

- The agent has inspected scraped context for the target product.
- Brand name is provided.
- Product name is provided.
- Weight is provided.
- Packaging is provided.

### Postconditions

- A simple `Product` exists in the catalog.
- Optional nutrition and store listing data are applied.

### Main success flow

1. The agent identifies a scraped item that should become a simple product.
2. The agent submits the product through GraphQL.
3. The GraphQL boundary normalizes the input.
4. The system creates the product through `ProductCreateService`.
5. Optional nutrition data is attached.
6. Optional store listing data is synchronized.

### Alternate flows

#### A1. Duplicate EAN

1. The system detects an existing product with the same EAN.
2. The system rejects creation with a validation error.

### Business rules

- Agent-driven creation goes through GraphQL as a thin boundary.
- Product creation remains owned by `ProductCreateService`.

## UC-03 Create Combo Product From Agent

### Goal

Create a combo product through GraphQL from scraped context.

### Primary actor

- AI Catalog Agent

### Supporting actors

- GraphQL boundary
- ProductCreateService
- ProductStoreService
- ComboResolutionService

### Trigger

- The agent submits a combo product with component data through GraphQL.

### Preconditions

- The agent has inspected scraped context for the combo.
- Brand name is provided.
- Product name is provided.
- Weight is provided.
- Packaging is provided.
- At least one component is provided.

### Postconditions

- A combo `Product` exists in the catalog.
- Optional store listing data is synchronized.
- Component links are created for the combo.

### Main success flow

1. The agent identifies a scraped item that should become a combo.
2. The agent submits the combo through GraphQL.
3. The GraphQL boundary normalizes the input.
4. The system creates the combo through `ProductCreateService`.
5. The system synchronizes optional store listings.
6. The system resolves combo components.

### Alternate flows

#### A1. Exact component match found

1. The system resolves a component by EAN or store `external_id`.
2. The system links the existing product as a component.

#### A2. Exact component match not found

1. The system cannot resolve a component.
2. The system creates an unpublished placeholder product.
3. The system links the placeholder as a component.

### Business rules

- Combo creation uses exact identifier matching for components.
- Fuzzy matching is intentionally not used.
- Placeholder products are unpublished support records.

## UC-04 Link Scraped Item To Product Store From Agent

### Goal

Link a scraped item to an explicitly chosen product store through the agent workflow.

### Primary actor

- AI Catalog Agent

### Supporting actors

- Scrapers GraphQL boundary
- ScrapedItemLinkService

### Trigger

- The agent chooses a scraped item and the target `ProductStore`.

### Preconditions

- The target `ProductStore` exists.
- A scraped item id is available.

### Postconditions

- The scraped item is linked to the chosen `ProductStore`.
- The scraped item status becomes `LINKED`.

### Main success flow

1. The agent submits the scraped item id and target `product_store_id`.
2. The system loads the selected `ProductStore`.
3. The system links the scraped item to the selected `ProductStore`.
4. The system marks the item as `LINKED`.
5. The system synchronizes price and stock into the core catalog.

### Alternate flows

#### A1. Product store does not exist

1. The chosen `product_store_id` does not resolve to a `ProductStore`.
2. The system returns no linked item.

#### A2. Scraped item does not exist

1. The chosen scraped item cannot be loaded.
2. The system returns no linked item.

### Business rules

- Linking is explicit; the service does not infer the target `ProductStore`.
- This workflow is exposed through `scrapers/graphql`, not `core/graphql`.
- Fuzzy matching is intentionally not used.
- Placeholder products are unpublished support records.
- Component management is coordinated through `ComboResolutionService`.

## Notes

- The AI agent uses GraphQL as its primary boundary.
- The agent depends on unlinked scraped items to decide where to search and what to create.
