Analyze all provided product images together and return an ordered image report.

Goal:
- recover visible text from each image when available
- identify what kind of image each one is
- preserve the original image order for downstream parsing

Rules:
- Do not hallucinate.
- If text is unreadable, say `not legible`.
- Prefer exact visible wording.
- Preserve numeric values and units exactly when visible.
- Use the image order exactly as received.
- The first image must be reported as `IMAGE_1`, the second as `IMAGE_2`, and so
  on.
- If an image appears to be a nutrition table, ingredients panel, front label,
  flavor selector, or combo banner, say so explicitly.
- If an image contains little or no useful text, still describe what kind of
  image it is.
- Include a short, concrete description of what the image is showing.
- When a flavor, variant, or package size is visible, mention it explicitly in
  the description.
- When the image is a combo or carousel frame, describe which products are
  visible in that frame.
- If a clue appears only in one image, keep it inside that image block instead
  of merging it with another image.

Output only Markdown.

For each image, emit exactly one block in this format and preserve the original
order:

## IMAGE_1
URL: <url from manifest when available>

### IMAGE DESCRIPTION
- one or two sentences describing what is visible in the image
- mention the main product, flavor, package size, and whether it looks like a
  front label, nutrition table, ingredients panel, combo frame, or decorative
  image

### IMAGE TYPE
- one or more of: front_label, product_packshot, nutrition_table,
  ingredients_panel, back_label, flavor_selector, combo_banner, lifestyle,
  unknown

### VISIBLE TEXT
- transcribe the important visible text
- preserve line breaks when useful

### STRUCTURED CLUES
- product names
- brand names
- flavor words
- variant words
- weights and units
- quantities or multipacks
- packaging clues
- combo or kit clues
- nutrition rows if visible
- ingredients if visible
- allergen warnings if visible

### CONFIDENCE
- overall confidence: high, medium, or low

Repeat the same block structure for `IMAGE_2`, `IMAGE_3`, and the remaining
images.
