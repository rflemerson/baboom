# Vision Table Selection (Current Pipeline)

Last updated: 2026-02-15

## Goal

Prioritize **high recall** for nutrition table images in product pages:

- Better to send extra images than to miss a real nutrition table.
- Keep enough context so the LLM can map table -> flavor/variant.

## Where It Runs

- Candidate extraction/scoring: `agents/tools/scraper.py`
- OCR image selection: `agents/assets.py` (`_select_images_for_ocr`)
- Sequence context sent to LLM: `agents/assets.py` (`_build_image_sequence_context`)

## Current Selection Logic

1. `scraper.py` pre-filters candidates:
   - dedupe by URL and perceptual hash
   - skip unsupported/small images (`<200x200`)
   - compute `score` + `nutrition_signal`
   - compute `cv_table_score` (lightweight table-structure heuristic):
     - long horizontal/vertical runs
     - line intersections density

2. `assets.py` focus and high-recall selection:
   - apply product focus using tokens from product name + URL path
   - collect likely tables using `_is_potential_table_candidate`
     - now includes `cv_table_score >= OCR_CV_TABLE_THRESHOLD`
   - with `OCR_INCLUDE_ALL_TABLES=1`, include:
     - all likely tables (up to `OCR_MAX_TABLE_CANDIDATES`)
     - neighboring images by `image_N` order (context)
   - append additional nutrition-scored images
   - fill remaining slots by relevance

3. Add `[IMAGE_SEQUENCE_CONTEXT]` to description before LLM:
   - image order
   - inferred kind (`NUTRITION_TABLE` / `PRODUCT_IMAGE`)
   - short hint from alt/title

## Tunables (Environment Variables)

- `OCR_INCLUDE_ALL_TABLES` (default `1`)
  - `1`: high-recall mode (can exceed base image cap)
  - `0`: strict cap behavior
- `OCR_MAX_TABLE_CANDIDATES` (default `24`)
- `OCR_CV_TABLE_THRESHOLD` (default `0.22`)
- `OCR_MAX_IMAGES` (default `12`)
- `OCR_MAX_NUTRITION_IMAGES` (default `8`)
- `OCR_MAX_IMAGES_NO_NUTRITION` (default `16`)

## Benchmark Notes

### CV-only experiments (offline prototype, not in production path)

Two experiments were run with OpenCV-style table structure features:

1. Curated set (`8` table, `20` non-table):
   - best matrix: `TP=8, FP=8, FN=0, TN=12`
   - recall `1.0`, precision `0.50`

2. Alternative structure scoring:
   - best matrix: `TP=8, FP=11, FN=0, TN=9`
   - recall `1.0`, precision `0.42`

Conclusion: CV-only is good for candidate generation, but too noisy for final decision.

### Real-page sweep (high-recall heuristic in production code)

Sample of 6 real product pages (Soldiers Nutrition):

- total candidates: `183`
- candidates flagged as potential table: `173`

This confirms current behavior is intentionally recall-heavy, with high false-positive potential.

## Operational Guidance

- For debugging extraction quality:
  - inspect `/tmp/baboom/<bucket>/candidates.json`
  - inspect image list sent in asset metadata (`images_sent`)
  - inspect sequence hints in raw extraction input

- For stricter behavior in constrained environments:
  - set `OCR_INCLUDE_ALL_TABLES=0`
  - reduce `OCR_MAX_TABLE_CANDIDATES`

## Next Improvements (without full OCR pipeline yet)

1. Tighten `_is_potential_table_candidate` with stronger positive terms and negative terms.
2. Add flavor/variant consistency checks before adding neighbor context.
3. Add fixture-based regression set with manually labeled real candidate manifests.
4. Keep high recall as default, but add per-store policy knobs.
