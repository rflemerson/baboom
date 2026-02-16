OBJECTIVE:
Analyze the provided IMAGES (label, nutrition table) and TEXT.
Extract everything you can about the product and organize it as STRUCTURED TEXT (Markdown).
Do not hallucinate. If it is not visible, do not include it.

YOUR SECTIONS MUST BE:

1. FULL NAME AND VARIATIONS
   - Main name, subtitles, slogans.

2. VISUAL METADATA
   - Net weight (e.g., 900g, 1.8kg)
   - Packaging type (Container, Refill, Bag, Bar)
   - Brand/Manufacturer
   - IS IT A KIT/COMBO? (Yes/No). If yes, describe items (e.g., "3x Whey 900g", "Buy 2 Get 1").

3. CATEGORIZATION (Inferred Hierarchy)
   - Extract category using a logical taxonomy tree.
   - For PROTEIN products, prefer: ["Protein", <Source: Animal/Plant>, <Type: Whey/Casein/Soy/etc>, <Process: Isolate/Concentrate/Hydrolyzed/Blend>]
   - Example 1: ["Protein", "Animal", "Whey", "Isolate"]
   - Example 2: ["Protein", "Plant", "Pea", "Concentrate"]
   - For other products, follow equivalent logic (e.g., ["Amino Acid", "Creatine", "Monohydrate"]).

4. AVAILABLE FLAVORS
   - List all flavors visible in image or text.

5. COMPLETE NUTRITION TABLE
   - Extract all core fields typically present in nutrition labels:
     - Serving size (e.g., 30g, 2 scoops)
     - Energy (kcal)
     - Carbohydrates (g) and Sugars (Total/Added)
     - Proteins (g)
     - Total/Saturated/Trans fats (g)
     - Dietary fiber (g)
     - Sodium (mg)
   - Also list all visible micronutrients, vitamins, minerals, and amino acids.

6. INGREDIENTS AND ALLERGENS
   - Ingredient list (if readable)
   - Allergen warnings (Contains gluten, milk, soy, etc.)

OUTPUT ONLY THE ORGANIZED TEXT. NO PREAMBLE.

IMAGE ASSOCIATION RULES (CRITICAL):
- You will receive an `[IMAGE_SEQUENCE_CONTEXT]` block with the exact order of images sent.
- When there are multiple nutrition tables, map each table to the correct product/variant.
- Prioritize association by:
  1) sequence proximity (table right after product image),
  2) explicit flavor mention,
  3) plain/unflavored vs flavored cues.
- DO NOT mix tables from different products.
- If association is uncertain, explicitly mark it as "uncertain association" instead of guessing.
