Analyze the input text report and return exactly one product object matching the
`ExtractedProduct` schema.

A scraped page always describes one root product. Do not return a list.

The input contains:

- `[SCRAPER_CONTEXT]` with deterministic store JSON
- `[ORDERED_IMAGE_REPORT]` with one ordered block per image

Use both sources together.
Prefer `[ORDERED_IMAGE_REPORT]` for visible packaging text, tables, ingredients,
allergens, flavors, weights, and combo composition.
Use `[SCRAPER_CONTEXT]` to confirm names, options, and store metadata when it
does not conflict with visible evidence.

### Product Tree Rule

- Return the page product as the root object.
- If the page describes a kit, combo, or bundle, put each included product in
  `children`.
- Each child uses the same product contract and may also have its own
  `children`.
- If there are no included products, return `children: []`.
- Do not create sibling products for flavors, sizes, nutrition tables, or
  variants.
- For combos, the root object must still be meaningfully filled.
- If the page title or packshot identifies the combo name, use it at the root.
- If the combo root has no single package weight, keep `weight_grams: null`.
- If the combo root is only a bundle container and not a real sellable package
  type, `packaging` may stay `OTHER`.
- When children are clearly identified, prefer rich child nodes over inventing
  synthetic root nutrition.

### Fields

Use these fields for the root product and every child:

- `name`
- `brand_name`
- `weight_grams`
- `packaging`: one of `CONTAINER`, `REFILL`, `BAR`, `OTHER`
- `quantity`
- `category_hierarchy`
- `tags_hierarchy`
- `nutrition_facts`
- `flavor_names`
- `variant_name`
- `children`

### Nutrition Data

- Extract nutrition table values precisely when visible.
- Use grams for serving size and macros.
- Use kcal for energy and mg for sodium.
- Use `0` for explicit zero values.
- Use `null` for `nutrition_facts` only when no reliable table is available for
  that product node.
- If only part of a table is visible, return partial `nutrition_facts` instead
  of dropping the entire object.
- If the report lists ingredients, allergen statements, dosage guidance, or
  guaranteed analysis but not a complete consumer nutrition table, preserve the
  useful remainder in `nutrition_facts.description`.
- Map common rows when visible:
  - serving size -> `serving_size_grams`
  - energy / valor energético -> `energy_kcal`
  - proteins / proteínas -> `proteins`
  - carbohydrates / carboidratos -> `carbohydrates`
  - total fats / gorduras totais -> `total_fats`
  - saturated fats / gorduras saturadas -> `saturated_fats`
  - trans fats / gorduras trans -> `trans_fats`
  - dietary fiber / fibra alimentar -> `dietary_fiber`
  - sodium / sódio -> `sodium`
- If a table contains one primary active ingredient such as creatine per
  serving and there is no dedicated numeric field for it, preserve it in
  `nutrition_facts.description`.

### Flavor And Variant Rules

- `flavor_names` should contain only explicit visible or option-level flavors.
- If a product is unflavored, use `["NO FLAVOR"]` only when that is clearly
  visible or strongly indicated by the report.
- `variant_name` is for subtype labels such as monohydrate, isolate, refill, or
  other meaningful product variants.
- Do not place the same concept redundantly in both `variant_name` and
  `flavor_names` unless the evidence clearly supports both.

### Category Rules

- Prefer a short but meaningful hierarchy over an empty list when the product
- type is clear.
- For simple products, use the visible product type and context.
- For combo roots, use a broad category only if it is defensible from the page;
  otherwise keep it empty and let the children carry the detailed categories.

### Image Report Rules

- `[ORDERED_IMAGE_REPORT]` may contain:
  - front packshots
  - combo frames
  - nutrition tables
  - ingredients panels
  - decorative images
- Ignore decorative images unless they add useful brand evidence.
- When a packshot is followed later by a nutrition or ingredients image for the
  same product/flavor, combine those facts into the same product node.
- For combo pages with repeated flavors in the carousel, aggregate the distinct
  flavors into the relevant child product instead of creating duplicate
  children.

### Data Integrity Rules

1. Do not invent values.
2. Keep arrays as arrays, even when empty.
3. Flavors and variants belong in `flavor_names` or `variant_name`; they do not
   become sibling products.
4. Children are only products physically included in a kit, combo, or bundle.
5. If unsure whether something is a child product, keep it out of `children`.
6. If the root page is a combo, do not collapse the whole page into one child.
7. When a child has reliable table data, attach the table to that child even if
   the root is only a bundle.
