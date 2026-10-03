# Pricing audit

What eight stores published about price on 2026-10-03, read from one linked
whey per store. Every row is one item, one endpoint, one moment: it shows what
that source exposed then, not what the platform or the store always exposes.

Fixtures under `scrapers/tests/fixtures/pricing/` keep the excerpts:

- `<store>.json` is a `source_excerpt`: the price, stock and variant fields of
  one item, with source URL, fetch time and the limits of the cut. It is not a
  normalizer input; `scrapers/tests/normalizers/test_pricing_fixtures.py`
  rebuilds the smallest input each normalizer accepts and checks which field
  becomes the offer price.
- `raw_text_matches` keeps every match of "pix" on a Shopify variant page,
  unclassified. Most are tracking pixels, theme scripts or related products.
- `benefits.json` is `selected_evidence`: verbatim excerpts, each tagged with
  what it proves (`evidence_level`) and what it covers (`applies_to`).

## Price fields per store

| Store | Platform | Becomes `current_price` | Reference ("de") | Price by payment method in this response | Installments in this response |
| --- | --- | --- | --- | --- | --- |
| Black Skull | VTEX | default seller `commertialOffer.Price` | `ListPrice` | `Installments[]`, one entry per payment system, Pix named | per card, interest stated |
| Max Titanium | VTEX | default seller `commertialOffer.Price` | `ListPrice` | `Installments[]`: Pix R$ 96.03 on a R$ 99.00 item | per card |
| Probiótica | VTEX | default seller `commertialOffer.Price` | `ListPrice` (equal to price) | `Installments[]`: Pix at full price | up to 6x, interest stated |
| Growth | Wap.Store | `precos.por`, falling back to `precos.vista` | `precos.de` | `precos.vista` + `descontoVista` (10%); method not named | `precos.parcelamento`, rate stated |
| DUX | Nuvemshop | `LS.variants[].price_number` | `compare_at_price_number` | `price_with_payment_discount_short` (5%), a formatted string; method not named | `installments_data` per gateway |
| Dark Lab | Shopify | `variant.price` (cents) | `compare_at_price` | none in `/products/<handle>.js`; the theme sets `pixDiscount = 10.0` | none in the endpoint |
| Integralmédica | Shopify | `variant.price` (cents) | `compare_at_price` (equal to price) | none in the endpoint; a collection is named "Pix 20%" | none in the endpoint |
| Soldiers | Shopify | `variant.price` (cents) | `compare_at_price` | none in the endpoint; theme attribute `data-pix-discount="5"` | the theme states both 6 and 3 on one page |

## Findings

- **The stored price has no single meaning.** Growth's falls back to the cash
  price when `por` is missing, so the history stays `legacy_unknown` until each
  observation carries its source field.
- **The VTEX catalog responses of these three items carried a price per payment
  method.** For them, the Pix price needed no cart simulation. That does not
  cover cart promotions, region, customer or quantity, and it is not a claim
  about every VTEX store.
- **The Shopify product endpoint of these three items carried no payment
  price.** Their payment discounts show only in the storefront theme. A theme
  value is evidence of what the store announces, not of what the checkout
  charges: Soldiers states two installment counts on one page.
- **Banners and catalog disagree.** Max Titanium announces 5% for Pix and
  boleto; its catalog priced Pix 3% lower. Probiótica announces "up to 5%";
  this whey had none.
- **At audit time the contract carried one price,** parsed through a float, and
  VTEX kept one seller per SKU. Both were fixed in delivery 3: every value in
  the table becomes a typed `OfferPriceObservation`, parsed to an exact
  decimal, and every VTEX seller is its own offer.

### Coverage of the cash scenario in this sample

| Evidence | Stores |
| --- | --- |
| A payment price in the store's own catalog response, method named | Black Skull, Max Titanium, Probiótica |
| A cash price in the catalog response, method not named | Growth, DUX |
| Only a storefront announcement | Dark Lab, Integralmédica, Soldiers |

One item per store, one moment. It says what each source can expose, not that
the dimension is covered for the store's whole catalog.

## VTEX cart simulation pilot

`POST /api/checkout/pub/orderForms/simulation` with one SKU, seller 1,
quantity 1, sales channel 1, country BRA and postcode 01310100.

| Store | Result |
| --- | --- |
| Black Skull | Answers. Item price equals the catalog; installment options per payment system; four delivery options with price and estimate |
| Max Titanium | 403 "Acesso bloqueado" |
| Probiótica | 403 "Acesso bloqueado" |

An earlier session saw Black Skull's catalog at R$ 119.90 and its cart at
R$ 99.90. This sample shows both at R$ 99.90. The gap was not reproduced; its
cause stays undetermined, since equal prices today cannot tell apart a
campaign change, a cache, a seller, a channel or a payment condition.

A 403 means access was unavailable for that request, not that the store has no
cart price. The simulation is not enabled in the crawl.

## Real promotions found

| Mechanic | Example | Evidence level |
| --- | --- | --- |
| Price by payment method | DUX: 5% applied automatically on Pix | terms |
| Price by payment method | Integralmédica: 5% on Pix | advertised |
| Percentage coupon, new customer, minimum | Integralmédica `PRIMEIRACOMPRA`: 20% on the first purchase above R$ 249, one order per CPF | advertised |
| Shipping benefit with minimum | Integralmédica: fixed shipping on that first purchase; free shipping above R$ 280 | advertised |
| Store-wide with exclusions | Integralmédica: a collection "Sem Évora XT \| Pix 20%" | collection name only |
| Compatibility rule | DUX: a gift card is not cumulative with payment-method promotions | terms |
| Points as store credit | Soldiers: points exchanged for a discount code, at most 750 points = R$ 60 per exchange, never for money | terms |

Still pending, not invented:

- **Monetary cashback with full terms.** DUX announces a cashback policy, but
  its regulation link redirects to the regulations index. Max Titanium's tiers
  (4%, 5%, 8%) appear only on a third-party coupon site.
- **Fixed-amount coupon with a minimum or cap** on an official page.
