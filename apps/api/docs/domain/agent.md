# Agent Extraction Review

This document describes the current backend contract for AI extraction. The
agent no longer creates catalog products directly.

## Scope

- The agents service checks out one `ScrapedItem`.
- Dagster reads `ScrapedPage.api_context` and `ScrapedPage.html_structured_data`.
- The agent returns one recursive product tree.
- Django stores the result in `ScrapedItemExtraction` for review.
- Catalog creation does not happen from the agent extraction flow.

## Main Flow

1. The agent calls `checkoutScrapedItem`.
2. Django locks one eligible `ScrapedItem`, marks it as `PROCESSING`, and returns
   source-page context.
3. Dagster extracts image text and converts the page context into one product
   tree.
4. The agent calls `submitAgentExtraction`.
5. Django validates the payload shape with scraper DTOs.
6. Django upserts `ScrapedItemExtraction` for the origin item.
7. Django marks the origin item as `REVIEW`.

## Error Flow

1. The agent calls `reportScrapedItemError` for the checked-out item.
2. Retryable errors move the item to `ERROR` and increment `error_count`.
3. Fatal errors move the item to `REVIEW`.
4. When retryable errors reach the max retry count, the item moves to `REVIEW`.

## GraphQL Mutations

```graphql
mutation CheckoutScrapedItem($data: ScrapedItemCheckoutInput!) {
  checkoutScrapedItem(data: $data) {
    id
    status
    sourcePageApiContext
    sourcePageHtmlStructuredData
  }
}
```

```graphql
mutation SubmitAgentExtraction($data: AgentExtractionInput!) {
  submitAgentExtraction(data: $data) {
    extraction {
      id
      scrapedItemId
      sourcePageId
      extractedProduct
    }
    errors {
      field
      message
    }
  }
}
```

```graphql
mutation ReportScrapedItemError($data: ScrapedItemErrorInput!) {
  reportScrapedItemError(data: $data)
}
```

Input fields:

- `originScrapedItemId`: required `ScrapedItem` id.
- `sourcePageId`: preferred source page id.
- `sourcePageUrl`: fallback when the item has no linked source page.
- `storeSlug`: store identifier used when a fallback source page must be created.
- `imageReport`: ordered image text produced by the multimodal step.
- `product`: recursive extracted product JSON.

Error input fields:

- `itemId`: required checked-out `ScrapedItem` id.
- `message`: error details.
- `isFatal`: whether the item should skip retries and move to review.

## Product Tree

Each page produces one product node:

```json
{
  "name": "Combo Whey + Creatina",
  "brandName": "Black Skull",
  "weightGrams": 1500,
  "packaging": "OTHER",
  "children": [
    {
      "name": "Whey",
      "brandName": "Black Skull",
      "weightGrams": 900,
      "children": []
    }
  ]
}
```

Rules:

- A simple product has `children: []`.
- A combo or kit is represented by children using the same schema.
- There is no `isCombo`, `items`, or `components` field in the agent contract.
- Nullable nutrition values are accepted because extraction evidence can be
  incomplete.

## Ownership

- `scrapers.models.ScrapedItemExtraction` persists the staged result.
- `scrapers.services.ScrapedItemExtractionSubmitService` owns validation and
  status changes.
- `scrapers.services.ScrapedItemErrorService` owns agent error reporting.
- Catalog product creation is currently owned by manager-facing admin workflows.
