# 🔄 Scraper Integration Roadmap

## Current State (Implemented ✅)

The scraper → core integration now follows this flow:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. SCRAPING (Automatic)                                        │
│     Spiders → ScrapedItem (status=NEW)                          │
├─────────────────────────────────────────────────────────────────┤
│  2. CURATION (Manual - Admin)                                   │
│     - Create Product + ProductStore                             │
│     - Link ScrapedItem to ProductStore                          │
│     - Set ScrapedItem.status = LINKED                           │
│     - Set Product.is_published = True (to show on website)      │
├─────────────────────────────────────────────────────────────────┤
│  3. PRICE SYNC (Automatic)                                      │
│     When ScrapedItem (LINKED) updates → ProductPriceHistory     │
│     (Only creates record if price/stock changed)                │
└─────────────────────────────────────────────────────────────────┘
```