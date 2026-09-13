Commands for explicit scraper maintenance live here; crawls and automatic data migrations do not.

`manage.py cutover_offer_identities` only previews the product-ID to unit-ID
mapping. After reviewing its output, `--apply` performs verified mappings in
one transaction. If any old offer lacks a unique evidenced unit, `--apply`
stops without writing; `--apply --archive-ambiguous` explicitly archives and
detaches those unresolved offers. Run it deliberately before the next
variant-level crawl when possible; deployment does not invoke it.

The cutover never renames an old `Offer` or copies its price history. The old
row and observations remain archived; a separate unit row receives any safe
curated link and starts with no price until the crawler observes it.
