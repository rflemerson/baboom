Analyze the RAW TEXT REPORT and return exactly one product object matching the
`ExtractedProduct` schema.

A scraped page always describes one root product. Do not return a list.

### Product Tree Rule

- Return the page product as the root object.
- If the page describes a kit, combo, or bundle, put each included product in
  `children`.
- Each child uses the same product contract and may also have its own
  `children`.
- If there are no included products, return `children: []`.
- Do not create sibling products for flavors, sizes, nutrition tables, or
  variants.

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
- Use `null` for `nutrition_facts` when no table is available for that product
  node.

### Data Integrity Rules

1. Do not invent values.
2. Keep arrays as arrays, even when empty.
3. Flavors and variants belong in `flavor_names` or `variant_name`; they do not
   become sibling products.
4. Children are only products physically included in a kit, combo, or bundle.
5. If unsure whether something is a child product, keep it out of `children`.
