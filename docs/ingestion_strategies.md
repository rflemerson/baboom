# Scraped Data Ingestion & Curation Strategies

The current scraper infrastructure is becoming "too effective", ingesting broad categories (all items) when the immediate focus is only on specific segments (e.g., Protein). This creates noise in the database and makes manual management difficult.

Below are three strategic approaches to handle this, analyzing the Pros, Cons, and my Recommendation.

---

## Strategy A: Staging Model ("Raw Data Layer")
**Concept**: Create a separate model (e.g., `ScrapedProduct` or `RawItem`) that acts as a staging area. Scrapers strictly write to this table. A separate process (or manual admin action) "promotes" items from Staging to the Production `Product` table.

### Structure
- **Model**: `ScrapedProduct` (JSONField for raw data, status field, distinct from `Product`).
- **Linking**: `ScrapedProduct` can have a ForeignKey to `Product` (nullable) to indicate "this raw item feeds this production product".

### Pros
- **Clean Core Data**: Your main `Product` table remains pristine. Only manually approved or high-confidence items enter it.
- **Safety**: Scraper bugs won't corrupt your live catalog.
- **History/Analytics**: You can keep a log of price changes in the raw layer without complex versioning in the main model.
- **Flexibility**: You can scrape *everything* now (Store it), and decide to use it later without re-scraping.

### Cons
- **Complexity**: Requires logic to "Sync/Promote" items.
- **Duplication**: Storing data twice (Raw vs Production).

---

## Strategy B: "Unreviewed" Status (Flagging)
**Concept**: Use the existing `Product` model but add a `status` or `is_verified` flag. Scrapers create items with `status='scraped_pending'`. The Admin Interface is customized to show a "Inbox" style view of new items.

### Structure
- **Model**: Update `Product` with `status = choices('published', 'draft', 'pending_review')`.
- **Admin**: Create a Custom Admin Filter or a separate Admin View solely for `pending_review` items.

### Pros
- **Simplicity**: No new models or sync logic.
- **Immediate Availability**: Once reviewed, it's live instantly.
- **Django Native**: Very easy to implement with standard Django Admin tools.

### Cons
- **Table Bloat**: Your main table grows large with "junk".
- **Pollution**: If not filtered correctly in Views/API, users might see junk data.

---

## Strategy C: Automatic Categorization + Smart Filtering
**Concept**: Continue scraping everything, but use sophisticated logic (Regex, Keyword Matching, or simple AI) during the *save* process to tag items. If an item doesn't match "Protein", auto-archive it or mark it as `low_priority`.

### Structure
- **Service**: Update `ScraperService` to classify items on save.
- **Logic**: `if 'whey' in name: priority=high else: priority=low`.

### Pros
- **Automation**: Reduces manual review time.
- **Focus**: You only see what matters.

### Cons
- **False Negatives**: Might miss interesting products if rules are too strict.

---

## Recommendation: The "Hybrid Staging" Approach

Considering your goal to focus on **Proteins** now but keep the door open for other categories later, I recommend **Strategy A (Staging Model)** combined with **Strategy C (Smart Filtering)**.

### Why?
1.  **Overload Protection**: You are fetching 30+ categories. Dumping all of that into your main `Product` table will make querying and management slow and messy.
2.  **Price History**: You explicitly mentioned linking price history. A `ScrapedProduct` (or `PriceObservation`) table is the *standard* way to track price over time without bloating the product row.
3.  **Workflow**:
    - **Scrapers** -> Insert/Update `ScrapedProduct` (Raw Data).
    - **Filter**: A background task (or Signal) checks: "Is this a Protein?"
        - **Yes**: Auto-create/Update `Product` (Core).
        - **No**: Leave in `ScrapedProduct` as "Ignored" (for now).

### Implementation Steps (Proposed)
1.  **Create `ScrapedItem` Model**:
    - Fields: `url` (unique), `raw_data` (JSON), `last_price`, `scraped_at`, `status` (New, Linked, Ignored).
2.  **Update `ScraperService`**:
    - Instead of `Product.objects.update_or_create`, do `ScrapedItem.objects.update_or_create`.
3.  **Admin Dashboard**:
    - A view to see `ScrapedItem` list.
    - "Promote" action to turn a `ScrapedItem` into a `Product`.
4.  **Price History**:
    - `ScrapedItem` effectively acts as your price log if you create a new row for each scrape (or a child `PriceHistory` model).

This gives you the best control: **Capture Everything, Curate selectivity.**
