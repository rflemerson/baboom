# Internal Use Cases

This document groups the internal automation use cases that support catalog maintenance.

## Actor: Internal Ingestion Workflow

### Description

- Explicit internal workflow that links scraped data to catalog entities after a
  target listing is chosen.

### Main goals

- link scraped items to explicitly chosen product store listings
- synchronize prices from scraped data into core entities

### Main entry points

- `ScrapedItemLinkService`
- `ScraperService`

## Scope

- link scraped items to chosen product store listings

## UC-01 Link Scraped Item To Product

### Goal

Link a scraped item to an explicitly selected product store listing.

### Primary actor

- Internal Ingestion Workflow

### Supporting actors

- ScrapedItemLinkService
- ScraperService
- Catalog Administrator
- AI Catalog Agent

### Trigger

- An actor chooses a scraped item and a target `ProductStore`.

### Preconditions

- The target `ProductStore` exists.
- A scraped item id is provided.

### Postconditions

- The scraped item is linked to the chosen `ProductStore`.
- The scraped item status becomes `LINKED`.

### Main success flow

1. The system receives a scraped item id and a chosen `product_store_id`.
2. The system loads the selected `ProductStore`.
3. The system loads the scraped item.
4. The system links the scraped item to the selected `ProductStore`.
5. The system updates the scraped item status to `LINKED`.
6. The system triggers price synchronization into the core catalog.

### Alternate flows

#### A1. Scraped item not found

1. The system cannot load the scraped item.
2. The system skips the linking workflow.

#### A2. Target product store does not exist

1. The chosen `product_store_id` does not resolve to a `ProductStore`.
2. The system skips the linking workflow.

### Business rules

- The service does not try to infer the target listing.
- The target `ProductStore` must be chosen by the admin workflow or the AI agent.
- Linking is coordinated through `scrapers.services.ScrapedItemLinkService`.

## Notes

- These flows are support workflows, not direct human-facing interfaces.
