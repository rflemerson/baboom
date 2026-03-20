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
- manage combo components

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

## UC-04 Manage Combo Components From Agent

### Goal

Maintain combo components through an agent-driven GraphQL workflow.

### Primary actor

- AI Catalog Agent

### Supporting actors

- GraphQL boundary
- ComboResolutionService

### Trigger

- The agent submits the desired set of combo components for a combo product.

### Preconditions

- The parent combo product exists.
- Component input rows are available.

### Postconditions

- The combo product has a synchronized set of `ProductComponent` links.

### Main success flow

1. The agent submits the desired component rows.
2. The GraphQL boundary normalizes the component input.
3. The system clears current component links for the combo.
4. For each submitted component, the system tries to resolve an existing product by exact identifiers.
5. If a product is found, the system links it as a component.
6. If no product is found, the system creates an unpublished placeholder product.
7. The system creates a `ProductComponent` row with the submitted quantity.

### Alternate flows

#### A1. Component resolved by EAN

1. The system finds a simple product with the provided EAN.
2. The system links that product as a component.

#### A2. Component resolved by external id

1. The system cannot resolve by EAN.
2. The system resolves the component by `external_id` within the combo store context.
3. The system links the resolved product.

#### A3. No exact match found

1. The system cannot resolve the component by exact identifiers.
2. The system creates an unpublished placeholder product.
3. The system links the placeholder as a component.

### Business rules

- Component management uses exact identifiers only.
- Fuzzy matching is intentionally not used.
- Placeholder products are unpublished support records.
- Component management is coordinated through `ComboResolutionService`.

## Notes

- The AI agent uses GraphQL as its primary boundary.
- The agent depends on unlinked scraped items to decide where to search and what to create.
