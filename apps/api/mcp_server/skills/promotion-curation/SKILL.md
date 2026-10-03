---
name: promotion-curation
description: Record a store's promotion, coupon, cashback or payment discount from evidence, through the admin MCP endpoint.
---

# Promotion curation

A promotion changes what a buyer pays at one store, or what they get back.
Curation records it from evidence and never guesses a term: an unknown end
date, stacking rule or exclusion stays unknown and goes in `limitations`.

## Steps

1. **Evidence.** Create an `offers.evidence` row: `kind` (announcement for a
   banner or promotions page, regulation for terms, theme_setting, manual),
   `source_url`, and the exact words in `excerpt`.
2. **Promotion.** Create `promotions.promotion` with a `title`, the issuer
   (`issuer_seller`: the store's seller account, found in
   `commerce.selleraccount` by its market namespace, which is the store slug)
   and a `source_key` naming the campaign at that store.
3. **Revision.** Create `promotions.promotionrevision` with `number` 1,
   `status` draft, `currency` (BRL in Brazil), `timezone`
   (America/Sao_Paulo), `verified_at` (when you read the evidence), `ends_at`
   only if the evidence states it, the `evidence`, and `conditions`.
4. **Owned rows,** while the revision is a draft: `activationcode` for a code,
   `promotionscope` for what it targets (role target) or what qualifies, and
   `promotioneffect` for what it grants. Cashback or points need
   `rewardterms` on the effect.
5. **Publish** by setting the revision's `status`: `executable` when the terms
   are complete enough to compute, `informative` when the promotion is real
   but its terms are not. A refused publication returns the reasons; fix them
   and set the status again.

## Conditions

A tree: `{"root": null}` for none, or `all`, `any`, `not` over leaves, e.g.

```json
{"root": {"all": [
  {"kind": "code_required"},
  {"kind": "new_customer", "issuer": "seller", "issuer_id": 12},
  {"kind": "min_amount", "amount": "249", "currency": "BRL",
   "basis": "before_discounts", "scope": "order"}
]}}
```

Leaves: `min_amount` (always with `basis` and `scope`), `min_quantity`,
`channel`, `market`, `seller`, `destination`, `payment_method` (codes such as
`pix`, `credit_card`, `boleto`), `program_member`, `subscription`,
`new_customer`, `calendar`, `code_required`.

## Effects

`kind` with `parameters`: `percentage` `{"rate": "20"}`, `fixed_amount`
`{"amount": "30"}`, `fixed_price` `{"price": "99.90"}`, `shipping_discount`
`{"free": true}`, `cashback` `{}` plus reward terms, `points`, `gift`,
`multibuy` `{"buy": 3, "pay": 2}`, `tiered`, `subscription`. A shipping
discount targets `shipping`; cashback and points use stage `reward`.

## Rules

- A published revision never changes. To correct it, run the promotion's
  "Start a new revision" action, edit the new draft, and publish it.
- Suspend or archive by status; never delete a published revision.
- A discount already inside an observed price (a Pix price the catalog
  publishes) is not a promotion to record again.
- Personal codes are `personal_code`; they never reach public rankings.
