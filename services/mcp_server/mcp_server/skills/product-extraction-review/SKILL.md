---
name: product-extraction-review
description: Review scraped Baboom products locally, stage evidence-backed drafts, and apply explicitly approved catalog links through the review MCP tools.
---

# Product Extraction Review

Use this skill when reviewing scraped products, one item at a time.

## What the catalog is for

Baboom ranks supplements by price per gram of an active, so the nutrition table
is the point. A product with a name, a price and no nutrition ranks nowhere.
Spend the effort there: the store API already gives you name, price, EAN and
stock, and it almost never gives you the label.

## Workflow

1. Discover items with `review_queue`. Use `checkout_scraped_item` when asked
   for the next item, or pass `item_id` for a specific queued one. Use
   `resume_item(item_id)` to reload a review without reserving it.
2. `prepare_current_item` returns what the scraper captured: parsed API context,
   structured data and image URLs.
3. When that context is thin -- common on sites that render client-side --
   `fetch_source_page` re-renders the page and returns JSON-LD blocks, meta
   tags, tables (nutrition tables usually land here as rows of text) and every
   image with its alt text.
4. Read name, brand, price, EAN and nutrition from the structured data. Prefer
   JSON-LD `Product` blocks that carry `offers`; blocks without offers are
   usually related-product shelves.
5. When the label is only in an image, pass the relevant images to
   `download_images` and then `create_image_report`. Judge relevance by URL, alt
   text and source. Treat the report as evidence, never as permission to guess.
6. Build the draft with `update_draft`, then `validate_draft`.
7. `build_submission_preview`, then `submit_draft(confirm=True)` only when the
   user says to send.
8. `report_item_error` when the item cannot be processed at all.

Send `act_on_current_item("heartbeat")` while working, before the 60-minute
inactivity timeout. `"release"` returns abandoned work to the queue; `"ignore"`
discards it deliberately.

## Deciding what to ignore

The queue contains everything the stores sell. Ignore, without extracting:
apparel, shakers, bottles, accessories, gift cards, and anything with no
ingestible content. They cannot rank and they pollute the catalog.

## Approving into the catalog

Staging is not approval. Submission stores evidence; approval changes the
catalog, and it needs a separate explicit confirmation.

1. Always search `catalog_candidates` by EAN, then by name, before proposing a
   new product. The same product sold by three stores must become one catalog
   product with three offers, not three products.
2. Resolve IDs with `catalog_choices` for brands, categories and tags.
3. Preview `approve_current_item(product_id=...)` to link an existing product,
   or `approve_current_item(create_product=...)` to create one.
4. Repeat with `confirm=True` only after the user approves that specific change.

`createProduct` takes `netMass` with its `massUnit` (grams unless the label says
otherwise); the API converts and stores canonically. Never send a converted
number. New products are always created unpublished.

## The catalog taxonomy

Categories live under `Suplementos`: Proteínas (Whey Protein, Caseína,
Albumina, Proteína Vegana, Proteína de Carne, Blend Proteico), Creatina,
Hipercalóricos, Aminoácidos (BCAA, Glutamina, Beta-Alanina, Aminoácidos
Essenciais), Pré-Treino, Termogênicos, Colágeno, Ômega e Óleos, Vitaminas e
Minerais, Barras e Snacks, Combos.

Pick the most specific category that fits. Do not invent categories; if nothing
fits, leave it unset and say so.

Brands are the eight scraped manufacturers. If a product's brand is not among
them, it is a resale item -- flag it rather than inventing a brand.

## Draft rules

- Extract only what the title, page, structured data or images actually show.
- Never guess an EAN. Never invent a nutrition value.
- `flavorNames` carries flavors; `variantName` carries a variation label.
- `children` is only for kits and combos made of distinct products.
- Nutrition is per label, not per product: two flavors printing the same table
  share one profile, and two flavors printing different tables are two profiles
  that get ranked independently. Keep each label's values with its flavors.
- Detailed nutrition, flavors and combo components are curated afterwards in
  Django admin. Keep the full evidence in the recursive draft so that curation
  has something to work from.
