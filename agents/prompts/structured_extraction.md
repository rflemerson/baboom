Analyze the following RAW TEXT REPORT (extracted from product images/description) and map it to the `ProductAnalysisList` schema.

Identify if the page offers multiple purchasing options (e.g. Unit vs Box, Flavors).
Return a valid JSON object containing a LIST of `items`.

### VARIANT DETECTION
- **Box/Kit**: If a "Box of 12" is available, create a separate Item in the list.
- **Flavors**: If different flavors are listed as *purchasable options*, create separate Items (or consolidate if just a list of available flavors).
- **Multiple Nutrition Tables**: When raw text indicates table-to-variant mapping, keep each table tied to the correct variant/item. Do not merge unrelated tables.

### PRODUCT NAMING & CLASSIFICATION
- **Name**: Extract the full, clean product name. Remove promotional slogans (e.g., "Melhor Preço").
- **Category Hierarchy**: Must be a list of strings representing the path.
  - Example: `["Proteína", "Animal", "Whey", "Concentrado"]`
  - For Creatine: `["Energia", "Creatina", "Monohidratada"]`
- **Packaging**: STRICTLY map to one of these enums:
  - `CONTAINER`: For tubs, pots, jars, cans.
  - `REFILL`: For pouches, bags, sachets.
  - `BAR`: For protein bars.
  - `OTHER`: Only if it doesn't fit above.

### NUTRITION DATA (CRITICAL)
- **Nutrient Claims**: Identify key nutrient drivers as slugs: `['protein', 'creatina', 'caffeine', 'glutamine']`.
- **Nutrition Facts**: Extract the TABLE values precisely.
  - **Serving Size**: Must be in grams (g) or ml.
  - **Macros**: Proteins, Carbs, Fats (Total, Saturated, Trans), Fiber, Sodium.
  - **Micros**: Vitamins and Minerals if prominent.
  - **Values**: Use `0` for implicitly missing values (e.g., "Does not contain saturated fat"). Use `null` only if the table is completely missing.

### COMBO & COMPONENTS
- **Is Combo**: Set to `true` if the item is a kit (e.g., "Kit 3x Whey", "Combo Mass").
- **Components**: If likely a combo, list the individual items found (e.g., `[{"name": "Whey Protein", "quantity": 3}]`).

### DATA INTEGRITY RULES
1. **No Hallucinations**: Do not invent values. If a flavor is not listed, do not guess.
2. **Numeric Parsing**: Convert text like "2,5g" to `2.5`. Ensure integers for KCAL and Sodium.
3. **Array Fields**: Always return arrays for `flavor_names`, `nutrient_claims`, and `tags_hierarchy`, even if empty `[]`.
4. **Table Association**: If there are multiple tables, prefer explicit flavor/natural markers and sequence clues from the raw report to map each table to the right item.
