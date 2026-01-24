---
name: product-registration
description: How to register products via GraphQL API
---

# Product Registration Skill

## Endpoint
```
POST /graphql/
Content-Type: application/json
```

## Full Mutation Template

```graphql
mutation CreateProduct {
  createProduct(data: {
    name: "Whey Protein Isolate"
    weight: 900
    brandName: "Growth Supplements"
    categoryName: "Whey Protein"
    ean: "7891234567890"
    description: "25g protein per serving"
    packaging: CONTAINER
    isPublished: false
    tags: ["Isolate", "Low Carb"]
    stores: [{
      storeName: "Amazon"
      productLink: "https://amazon.com.br/dp/B123456"
      externalId: "B123456"
      affiliateLink: "https://amzn.to/abc123"
      price: 199.90
      stockStatus: AVAILABLE
    }]
    nutrition: [{
      flavorNames: ["Chocolate", "Baunilha"]
      nutritionFacts: {
        description: "Porção padrão"
        servingSizeGrams: 30
        energyKcal: 120
        proteins: 25.0
        carbohydrates: 2.0
        totalSugars: 1.0
        addedSugars: 0.0
        totalFats: 1.5
        saturatedFats: 0.5
        transFats: 0.0
        dietaryFiber: 0.0
        sodium: 50
        micronutrients: [
          { name: "Vitamina B6", value: 1.3, unit: "mg" },
          { name: "Ferro", value: 2.5, unit: "mg" }
        ]
      }
    }]
  }) {
    product {
      id
      name
      brand { name }
    }
    errors {
      field
      message
    }
  }
}
```

## Field Reference

### ProductInput (Required fields marked with ✅)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | String | ✅ | - | Product display name |
| `weight` | Int | ✅ | - | Weight in grams |
| `brandName` | String | ✅ | - | Brand name (auto-created if missing) |
| `categoryName` | String | ❌ | null | Category name (auto-created as root) |
| `ean` | String | ❌ | null | Barcode (must be unique) |
| `description` | String | ❌ | "" | Marketing description |
| `packaging` | Enum | ❌ | CONTAINER | REFILL, CONTAINER, BAR, OTHER |
| `isPublished` | Bool | ❌ | false | Visible on public site |
| `tags` | [String] | ❌ | [] | Tag names (auto-created) |
| `stores` | [ProductStoreInput] | ❌ | [] | Store links with prices |
| `nutrition` | [ProductNutritionInput] | ❌ | [] | Nutrition profiles |

### ProductStoreInput

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `storeName` | String | ✅ | - |
| `productLink` | String | ✅ | - |
| `price` | Float | ✅ | - |
| `externalId` | String | ❌ | "" |
| `affiliateLink` | String | ❌ | null |
| `stockStatus` | Enum | ❌ | AVAILABLE |

### StockStatusEnum
- `AVAILABLE` (A)
- `LAST_UNITS` (L)
- `OUT_OF_STOCK` (O)

### NutritionFactsInput

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `servingSizeGrams` | Int | ✅ | - |
| `energyKcal` | Int | ✅ | - |
| `proteins` | Float | ✅ | - |
| `carbohydrates` | Float | ✅ | - |
| `totalFats` | Float | ✅ | - |
| `description` | String | ❌ | "" |
| `totalSugars` | Float | ❌ | 0.0 |
| `addedSugars` | Float | ❌ | 0.0 |
| `saturatedFats` | Float | ❌ | 0.0 |
| `transFats` | Float | ❌ | 0.0 |
| `dietaryFiber` | Float | ❌ | 0.0 |
| `sodium` | Int | ❌ | 0 |
| `micronutrients` | [MicronutrientInput] | ❌ | [] |

## Error Handling

The mutation returns `ProductResult`:
```json
{
  "product": { ... } | null,
  "errors": [{ "field": "ean", "message": "EAN already exists" }] | null
}
```

### Common Errors
| Error | Meaning | Action |
|-------|---------|--------|
| "EAN already exists" | Product with this barcode exists | Skip or update |
| "Product with this brand, name, and weight already exists" | Duplicate product | Skip |

## Workflow for LLM Agent

1. **Navigate** to product page using browser
2. **Extract** data from DOM (name, price, weight, nutrition table)
3. **Map** to `ProductInput` structure
4. **Send** mutation via POST to `/graphql/`
5. **Check** response for errors
6. If error: log and continue to next product
7. If success: log product ID created

## Example cURL

```bash
curl -X POST http://localhost:8000/graphql/ \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { createProduct(data: { name: \"Test\", weight: 500, brandName: \"Brand\" }) { product { id } errors { field message } } }"}'
```

---

## Update Existing Product (Content Only)

> **IMPORTANT**: Use this mutation to enrich existing products. It does NOT touch prices.
> Scrapers are the authority on prices, LLM is the authority on content.

```graphql
mutation UpdateProductContent {
  updateProductContent(productId: 123, data: {
    description: "Enhanced description with more details"
    categoryName: "Whey Protein Isolado"
    tags: ["Isolate", "Low Carb", "25g Protein"]
  }) {
    product {
      id
      name
      lastEnrichedAt
    }
    errors {
      field
      message
    }
  }
}
```

### ProductContentUpdateInput

| Field | Type | Description |
|-------|------|-------------|
| `name` | String? | New name (optional) |
| `description` | String? | New description (optional) |
| `categoryName` | String? | New category (empty string clears) |
| `packaging` | Enum? | REFILL, CONTAINER, BAR, OTHER |
| `tags` | [String]? | Replaces all tags |

### When to Use Which Mutation

| Scenario | Mutation |
|----------|----------|
| New product from scraping | `createProduct` |
| Enrich existing product metadata | `updateProductContent` |
| Update price | ❌ Don't use GraphQL, use scraper |

