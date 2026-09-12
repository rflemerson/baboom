---
name: product-extraction-review
description: Curate scraped Baboom products through Django's admin REST API.
---

# Product curation

Baboom ranks supplements by price per gram of an active. Nutrition evidence is
therefore the goal: a product with a name and price but no nutrition cannot
rank.

## Workflow

1. Use `admin_registry` to discover the models and actions available to the
   signed-in catalog operator.
2. Read the merchant offer and its related `ScrapedPage` through `admin_list`
   or `admin_get`.
3. If `raw_html` is empty, call the registered page-enrichment action with
   `admin_action` on that page. The render runs in Django's worker.
4. Read the refreshed page and pass its `raw_html` to `parse_page` for tables,
   visible text, and image references.
5. When nutrition exists only in an image, use `download_images` and then
   `create_image_report` with a local working directory. Treat the report as
   evidence and never invent a value.
6. Create or edit the catalog product with `admin_create` or `admin_update`.
   Send the mass value together with its `massUnit`; Django canonicalizes it.
   Products remain unpublished until a human publishes them.
7. Use `admin_autocomplete` for brands, categories, actives, stores, flavors,
   and tags instead of guessing primary keys.

The admin API uses the permissions of the signed-in user. A 403 means the
operator's group lacks permission and must be handled as such; it is not a
network error to work around.

## Catalog rules

- The same product sold by three stores is one catalog product with three
  offers. Search by EAN and then by name before creating a new product.
- Nutrition belongs to a label. Different labels on one product are separate
  nutrition profiles and must be linked to the flavors that print each label.
- Extract only values shown by the offer, captured page, structured data, or
  images. Never guess an EAN, brand, serving size, or nutrient.
- Ignore apparel, shakers, bottles, accessories, gift cards, and anything with
  no ingestible content. They cannot rank and do not belong in the catalog.
