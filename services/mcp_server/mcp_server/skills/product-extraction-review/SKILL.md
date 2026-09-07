---
name: product-extraction-review
description: Review scraped Baboom products locally, stage evidence-backed drafts, and apply explicitly approved catalog links through the review MCP tools.
---

# Product Extraction Review

Use this skill when reviewing one scraped product.

## Goal

Prepare an extraction draft, stage it when requested, and apply catalog changes
only after explicit approval of a concrete existing-product link or new product.

## Workflow

1. Discover items with `review_queue`. Use `checkout_scraped_item` when the user
   asks to work on the next item, or pass `item_id` for selected queued work.
   Use `resume_item(item_id)` to reload an existing review without reserving it.
2. Use `prepare_current_item` to get the structured context scraped for the item (parsed API context, structured data, image URLs).
3. If the context is missing or insufficient (common on sites that only load content client-side), use `fetch_source_page`. It returns the rendered page as structured data: JSON-LD blocks, meta tags, tables (nutrition tables usually appear here as rows of text) and every referenced image with its alt text and where it was referenced. The raw `page.html` and `page_data.json` are also saved in the item's workspace.
4. Read the product details (name, brand, price, EAN, nutrition facts) directly from the structured data. Prefer JSON-LD `Product` blocks that have `offers` — blocks without offers are usually related-product shelves.
5. Pick the images that matter as visual evidence (product photos, nutrition label images — judge by URL, alt text and source) and pass them to `download_images`. Then use `create_image_report` to analyze them with the vision model.
6. Use the image report as evidence, but do not invent fields.
7. Build or update the local draft using `update_draft`.
8. Use `build_submission_preview` before submitting.
9. Only call `submit_draft` (passing `confirm=True`) when the user explicitly says to send.
10. Use `report_item_error` if the item cannot be processed.
11. Search `catalog_candidates` by EAN and/or name before proposing creation.
    Resolve brand/category/tag IDs with `catalog_choices`.
12. Preview `approve_current_item(product_id=...)` or
    `approve_current_item(create_product=...)`. Only repeat with `confirm=True`
    after the user approves that catalog change. Submission to staging is not
    approval to create a catalog product.

While an item is processing, use `act_on_current_item("heartbeat")` before the
60-minute inactivity timeout. Release abandoned work with `"release"`; use
`"ignore"` for deliberately discarded items. Resume preserves local edits and
restores the server draft/report only when the corresponding local files are absent.

Created catalog products are unpublished and use explicit basic metadata. Detailed
nutrition, flavors, and combo components are curated in Django admin; retain that
evidence in the recursive extraction draft.

## Draft rules

- Prefer explicit information from title, source page, structured data, and images.
- Do not guess EAN.
- Do not invent nutrition facts.
- Use `children` only for kits/combos with distinct products.
- Use `flavorNames` for flavors.
- Use `variantName` for variation labels.
