# Pricing

The normative index of the pricing domain: what a price means, how promotions,
rewards and shipping change what a buyer pays, and how the catalog ranks it.
The domain covers independent stores and marketplaces in any market; the eight
stores crawled today are integration samples, not its definition.

- [Audit](./pricing-audit.md): what each sampled store published on
  2026-10-03, with fixtures.

## Decisions

- **Default ranking, target:** the lowest public price paid at once, for one
  purchasable unit, with no membership, first-purchase, subscription, coupon or
  cashback requirement. The payment method behind it is always shown.
- **Default ranking, until observations carry their meaning:** the price the
  store reports (`Offer.current_price`), only among offers in a purchasable
  state (`StockStatus.purchasable()`, an allowlist). Prices of unknown meaning
  are not relabelled as unconditional.
- **Selectable scenarios:** cash, a given payment method, installments,
  coupons, cashback, quantity and shipping. A payment discount already
  included in an observed price is never applied again.
- **Buyer context:** no server-side profile. Preferences live in the browser
  and travel with each query. Only public, shareable options (scenario,
  quantity, payment method) go in the URL; postcode, personal codes and
  eligibility claims never do. A card is described by its programme, not its
  data. "New customer" is a per-store, per-programme claim of the user, never
  confirmed.
- **Curation:** humans in the admin and agents over MCP write through the same
  validation. Source, verification date, known conditions and limits exist
  from the first version. A promotion with incomplete terms is stored as
  informative; only one with sufficient terms and supported effects enters a
  calculation. That is a field and a state, not a separate approval flow.
- **Revisions:** promotion terms are versioned from the start. A published
  revision is immutable, including its scopes, codes, effects and
  compatibility; an edit publishes a new revision. A persisted quote keeps the
  revisions, observations, policy and engine version it used.
- **Scope of the model:** the full domain is modelled; only the implementation
  is incremental. An effect the engine cannot compute yet returns
  `unsupported`, and missing data returns `unknown`, never a silent value.
- **Evidence:** an announcement, a regulation, a theme setting, a catalog
  response and a cart quote prove different things, and each fact records
  which one it rests on. A coincidence observed today is not the cause of a
  past difference.
