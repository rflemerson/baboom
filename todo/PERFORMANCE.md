# ⚡ Performance Tasks

## [PERF-001] Cache Protein Concentration Calculations
**Priority:** Medium
**Context:**
Currently, `ProductQuerySet.with_stats` calculates protein concentration on every query using DB annotations:
```python
(F("per_serving_protein") / F("serving_size_val")) * 100
```
While efficient for DB-side execution, frequent reads on high-traffic pages can benefit from caching.

**Action Items:**
- [ ] **Analyze**: Determine if we should cache the *queryset result* (e.g., template fragment cache) or the *computed value* (denormalization).
- [ ] **Implement**:
    - Option A (Low Effort): Use Django's `cache_page` or `{% cache %}` in templates.
    - Option B (Robust): Add a `cached_concentration` field to `Product` model and update it via `post_save` signals on `NutritionFacts` changes.
- [ ] **Verify**: Ensure the value updates when nutrition info changes.

## [PERF-002] Optimize Static Asset Delivery
**Priority:** Low
**Action Items:**
- [ ] Verify `WhiteNoise` compression settings (Brotli/Gzip).
- [ ] Implement browser caching headers (Cache-Control) for static files.
