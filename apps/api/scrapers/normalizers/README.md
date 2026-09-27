# Scraper normalizers

Normalizers convert a store payload into the scraper contracts. They do not
access Django, persistence services, or database models. A product returned by
a normalizer represents one source page; each offer represents one unit that
the store prices and sells independently.
An identified unit without a usable price is retained as unavailable so its
previous sale price is cleared. Only an exhaustive, successfully parsed unit
list (Shopify, VTEX, a Wap.Store `simples` attribute, a Nuvemshop product page)
sets `complete_unit_list` for reconciliation.
