# Scraper normalizers

Normalizers convert a store payload into the scraper contracts. They do not
access Django, persistence services, or database models. A product returned by
a normalizer represents one source page; each offer represents one unit that
the store prices and sells independently.

The Wap.Store normalizer still has an unresolved source-data limitation: it is
not verified whether `item.id` identifies a product or a buyable unit.
