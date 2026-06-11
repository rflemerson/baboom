# Product Extraction Review

Use this skill when reviewing one scraped product.

## Goal

Prepare a clean extraction draft and submit it to review staging only after user confirmation.

## Workflow

1. Use `checkout_scraped_item` when the user asks for the next item.
2. Use `prepare_current_item` to get the structured context scraped for the item (parsed API context, structured data, image URLs).
3. If the context is missing or insufficient (common on sites that only load content client-side), use `fetch_source_page`. It returns the rendered page as structured data: JSON-LD blocks, meta tags, tables (nutrition tables usually appear here as rows of text) and every referenced image with its alt text and where it was referenced. The raw `page.html` and `page_data.json` are also saved in the item's workspace.
4. Read the product details (name, brand, price, EAN, nutrition facts) directly from the structured data. Prefer JSON-LD `Product` blocks that have `offers` — blocks without offers are usually related-product shelves.
5. Pick the images that matter as visual evidence (product photos, nutrition label images — judge by URL, alt text and source) and pass them to `download_images`. Then use `create_image_report` to analyze them with the vision model.
6. Use the image report as evidence, but do not invent fields.
7. Build or update the local draft using `update_draft`.
8. Use `build_submission_preview` before submitting.
9. Only call `submit_draft` (passing `confirm=True`) when the user explicitly says to send.
10. Use `report_item_error` if the item cannot be processed.

## Draft rules

- Prefer explicit information from title, source page, structured data, and images.
- Do not guess EAN.
- Do not invent nutrition facts.
- Use `children` only for kits/combos with distinct products.
- Use `flavorNames` for flavors.
- Use `variantName` for variation labels.
