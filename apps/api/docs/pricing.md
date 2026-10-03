# Pricing

What the stores publish about price, what the catalog stores today, and the
decisions that shape the pricing domain. The architecture is the one in the
pricing research of 2026-10-03 (observed prices, promotions with conditions,
scopes, effects, compatibility, rewards, evidence and context); this file
records the audit that grounds it and the product decisions taken on it.

## Decisions

- **Default ranking, target:** the lowest public price paid at once, for one
  available unit, with no first-purchase, subscription, coupon or cashback
  requirement. The payment method behind it is always shown.
- **Default ranking, until the audit coverage below is closed:** the price the
  store reports today (`Offer.current_price`), only among offers in stock.
  Prices of unknown meaning are not relabelled as unconditional.
- **Selectable scenarios:** cash, a given payment method, installments,
  coupons, cashback, quantity and shipping. A payment discount already
  included in an observed price is never applied again.
- **Buyer context:** no server-side profile. Preferences live in the browser
  and travel with each query. Only public, shareable options (scenario,
  quantity, payment method) go in the URL; postcode, personal codes and
  eligibility claims never do. A card is described by its programme, not its
  data. "New customer" is a per-store claim of the user, never confirmed.
- **Curation:** humans in the admin and agents over MCP write through the same
  validation. Source, verification date, known conditions and limits exist
  from the first version. A promotion with incomplete terms is stored as
  informative; only one with sufficient terms and supported effects enters a
  calculation. That is a field and a state, not a separate approval flow.
- **Revisions:** a persisted quote must keep a snapshot of the terms and inputs
  it used. Until quotes are persisted, revision storage can wait.
- **Scope of the model:** the full domain is modelled; only the implementation
  is incremental. An effect the engine cannot compute yet returns
  `unsupported` or `unknown`, never a silent value.

## Availability

`core.selectors` prices a product by the cheapest listed offer that is in
stock. Sold-out offers do not compete; a published product without one keeps
its row, without a price.

## Audit of price fields per store

Fixtures under `scrapers/tests/fixtures/pricing/` hold the real payload of one
linked whey per store, cut to price, stock and variant fields, with source URL
and fetch date (2026-10-03).

| Store | Platform | Stored today as `current_price` | Reference ("de") | Price by payment method | Installments |
| --- | --- | --- | --- | --- | --- |
| Black Skull | VTEX | `commertialOffer.Price` | `ListPrice` | `Installments[]`, one entry per payment system, Pix named | per card, interest stated |
| Max Titanium | VTEX | `commertialOffer.Price` | `ListPrice` | `Installments[]`: Pix R$ 96.03 on a R$ 99.00 item | per card |
| Probiótica | VTEX | `commertialOffer.Price` | `ListPrice` (equal to price) | `Installments[]`: Pix at full price | up to 6x, interest stated |
| Growth | Wap.Store | `precos.por`, falling back to `precos.vista` | `precos.de` | `precos.vista` + `descontoVista` (10%); method not named | `precos.parcelamento`, rate stated |
| DUX | Nuvemshop | `LS.variants[].price_number` | `compare_at_price_number` | `price_with_payment_discount_short` (5%); method not named in the field | `installments_data` per gateway |
| Dark Lab | Shopify | `variant.price` (cents) | `compare_at_price` | not in the API; the storefront theme sets `pixDiscount = 10.0` | not in the API |
| Integralmédica | Shopify | `variant.price` (cents) | `compare_at_price` (equal to price) | not in the API; a collection named "Pix 20%" | not in the API |
| Soldiers | Shopify | `variant.price` (cents) | `compare_at_price` | not in the API; theme attribute `data-pix-discount="5"` | theme states both 6 and 3 on one page |

### What this means

- **The legacy price has no single meaning.** Growth's falls back to the cash
  price when `por` is missing, so history stays `legacy_unknown` until each
  observation carries its source field.
- **VTEX already publishes the price per payment method in the catalog.** The
  cart simulation is not needed to know the Pix price.
- **Shopify does not.** Its payment discounts live in the storefront theme or
  the checkout. A theme value is evidence of what the store announces, not of
  what the checkout charges: Soldiers states two installment counts on one
  page.
- **Banners and catalog can disagree.** Max Titanium announces 5% for Pix and
  boleto; its catalog prices Pix 3% lower. Probiótica announces "up to 5%";
  this whey has none.
- **Cash scenario coverage:** from the store's own data for 5 of 8 stores (the
  three VTEX by method, Growth and DUX as "cash" with the method unnamed);
  only from storefront announcements for the 3 Shopify stores. The cash
  scenario can be enabled once each price carries its source and evidence
  level, with the Shopify stores labelled as announced.

## VTEX cart simulation pilot

`POST /api/checkout/pub/orderForms/simulation` with one SKU, seller 1,
quantity 1, sales channel 1, country BRA and postcode 01310100.

| Store | Result |
| --- | --- |
| Black Skull | Answers. Item price equals the catalog; installment options per payment system; four delivery options with price and estimate |
| Max Titanium | 403 "Acesso bloqueado" |
| Probiótica | 403 "Acesso bloqueado" |

The earlier gap between Black Skull's catalog (R$ 119.90) and cart (R$ 99.90)
is gone: both now read R$ 99.90, so it was the moment a promotion reached the
catalog, not a lasting difference. The simulation is useful for cart-level
promotions and for shipping quotes, and only where the store allows it. It is
not enabled in the crawl.

## Real promotions found

`scrapers/tests/fixtures/pricing/benefits.json` keeps each with its source,
date, verbatim excerpts and what remains unknown.

| Mechanic | Example |
| --- | --- |
| Price by payment method | DUX: 5% applied automatically on Pix; Integralmédica: 5% on Pix |
| Percentage coupon, new customer, minimum | Integralmédica `PRIMEIRACOMPRA`: 20% on the first purchase above R$ 249, one order per CPF |
| Shipping benefit with minimum | Integralmédica: fixed shipping on that first purchase; free shipping above R$ 280 |
| Store-wide with exclusions | Integralmédica: a collection "Sem Évora XT \| Pix 20%" (name only, terms unknown) |
| Compatibility rule | DUX: a gift card is not cumulative with payment-method promotions |
| Points as store credit | Soldiers: points exchanged for a discount code, at most 750 points = R$ 60 per exchange, never for money |

Still pending, not invented:

- **Monetary cashback with full terms.** DUX announces a cashback policy, but
  its regulation link redirects to the regulations index. Max Titanium's tiers
  (4%, 5%, 8%) appear only on a third-party coupon site.
- **Fixed-amount coupon with a minimum or cap** on an official page.
